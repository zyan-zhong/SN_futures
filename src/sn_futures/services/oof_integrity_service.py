from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .institutional_validation_service import (
    bootstrap_reality_check,
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
)


DEFAULT_HORIZONS = ("1d", "3d", "5d", "10d", "20d")
CONFIDENCE_LEVELS = (0.10, 0.20, 0.30)
MAX_DRAWDOWN_ABS = 0.35


def _output_dir() -> Path:
    return get_user_output_dir()


def _normalise_version(version: str | None) -> str:
    value = str(version or "v1").strip().lower()
    return value or "v1"


def _walk_forward_dir(candidate_version: str | None = "v1") -> Path:
    version = _normalise_version(candidate_version)
    path = _output_dir() / "walk_forward"
    return path if version == "v1" else path / version


def _report_path(candidate_version: str | None = "v1") -> Path:
    version = _normalise_version(candidate_version)
    path = _output_dir() / "oof_integrity"
    if version != "v1":
        path = path / version
    path.mkdir(parents=True, exist_ok=True)
    return path / "oof_integrity_report.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _read_trace(horizon: str, candidate_version: str = "v1") -> pd.DataFrame:
    path = _walk_forward_dir(candidate_version) / f"oof_trace_{horizon}.csv"
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def _load_manifest(dataset_version: str = "v1") -> Mapping[str, Any]:
    version = _normalise_version(dataset_version)
    name = "training_dataset_manifest.json" if version == "v1" else f"training_dataset_manifest_{version}.json"
    payload = _read_json(_output_dir() / name)
    return payload if isinstance(payload, Mapping) else {}


def _load_wf(horizon: str, candidate_version: str = "v1") -> Mapping[str, Any]:
    payload = _read_json(_walk_forward_dir(candidate_version) / f"wf_{horizon}.json")
    return payload if isinstance(payload, Mapping) else {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _num_col(frame: pd.DataFrame, column: str, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series([default] * len(frame), index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(default)


def _strategy_returns(frame: pd.DataFrame) -> np.ndarray:
    if frame.empty:
        return np.asarray([], dtype=float)
    pred = _num_col(frame, "predicted_direction").astype(int).to_numpy()
    returns = _num_col(frame, "realized_return").to_numpy(dtype=float)
    costs = _num_col(frame, "cost_assumption").to_numpy(dtype=float)
    return np.where(pred != 0, np.sign(pred) * returns - costs, 0.0)


def _max_drawdown(values: np.ndarray) -> float:
    if values.size == 0:
        return 0.0
    equity = np.cumsum(values)
    return float(np.min(equity - np.maximum.accumulate(equity)))


def _accuracy(frame: pd.DataFrame) -> float | None:
    if frame.empty:
        return None
    selected = frame[_num_col(frame, "predicted_direction").astype(int) != 0]
    if selected.empty:
        return None
    pred = _num_col(selected, "predicted_direction").astype(int).to_numpy()
    actual = np.sign(_num_col(selected, "realized_direction").astype(int).to_numpy())
    return float((np.sign(pred) == actual).mean())


def _balanced_accuracy(frame: pd.DataFrame) -> float | None:
    if frame.empty:
        return None
    selected = frame[_num_col(frame, "predicted_direction").astype(int) != 0]
    if selected.empty:
        return None
    pred = np.sign(_num_col(selected, "predicted_direction").astype(int).to_numpy())
    actual = np.sign(_num_col(selected, "realized_direction").astype(int).to_numpy())
    recalls = []
    for label in (-1, 1):
        mask = actual == label
        if mask.any():
            recalls.append(float((pred[mask] == label).mean()))
    return float(np.mean(recalls)) if recalls else None


def _precision(frame: pd.DataFrame, label: int) -> float | None:
    if frame.empty:
        return None
    selected = frame[_num_col(frame, "predicted_direction").astype(int) == label]
    if selected.empty:
        return None
    actual = np.sign(_num_col(selected, "realized_direction").astype(int).to_numpy())
    return float((actual == label).mean())


def _hit_by_group(frame: pd.DataFrame, key: str) -> list[dict[str, Any]]:
    if frame.empty or key not in frame.columns:
        return []
    rows: list[dict[str, Any]] = []
    for name, group in frame.groupby(frame[key].fillna("UNKNOWN").astype(str), observed=True):
        rows.append(
            {
                key: name,
                "sample_count": int(len(group)),
                "signal_count": int((_num_col(group, "predicted_direction").astype(int) != 0).sum()),
                "accuracy": _accuracy(group),
                "expectancy": float(np.mean(_strategy_returns(group))) if len(group) else None,
            }
        )
    return sorted(rows, key=lambda row: row["sample_count"], reverse=True)


def _year_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    work = frame.copy()
    work["year"] = pd.to_datetime(work.get("label_start_time"), errors="coerce").dt.year.fillna(0).astype(int).astype(str)
    return _hit_by_group(work, "year")


def _subset(frame: pd.DataFrame, coverage: float) -> pd.DataFrame:
    if frame.empty:
        return frame
    work = frame.copy()
    work["confidence"] = _num_col(work, "confidence")
    cutoff = work["confidence"].quantile(max(0.0, min(1.0, 1.0 - coverage)))
    return work[work["confidence"] >= cutoff].copy()


def _subset_metrics(frame: pd.DataFrame, coverage: float) -> dict[str, Any]:
    sub = _subset(frame, coverage)
    returns = _strategy_returns(sub)
    fold_rows = _hit_by_group(sub, "fold_id")
    regime_rows = _hit_by_group(sub, "regime_label")
    year_rows = _year_rows(sub)
    worst_fold = min((row["accuracy"] for row in fold_rows if row.get("accuracy") is not None), default=None)
    worst_regime = min((row["accuracy"] for row in regime_rows if row.get("accuracy") is not None), default=None)
    worst_year = min((row["accuracy"] for row in year_rows if row.get("accuracy") is not None), default=None)
    realized_source = sub["realized_return"] if "realized_return" in sub.columns else pd.Series(dtype=float)
    realized_returns = pd.to_numeric(realized_source, errors="coerce").dropna()
    holding = str(frame.get("horizon", pd.Series([""])).iloc[0]) if not frame.empty and "horizon" in frame.columns else ""
    return sanitize_for_json(
        {
            "coverage": coverage,
            "sample_count": int(len(sub)),
            "actual_coverage": float(len(sub) / max(len(frame), 1)) if len(frame) else 0.0,
            "direction_accuracy": _accuracy(sub),
            "balanced_accuracy": _balanced_accuracy(sub),
            "precision_up": _precision(sub, 1),
            "precision_down": _precision(sub, -1),
            "realized_return_mean": float(realized_returns.mean()) if not realized_returns.empty else None,
            "realized_return_median": float(realized_returns.median()) if not realized_returns.empty else None,
            "cost_adjusted_expectancy": float(np.mean(returns)) if returns.size else None,
            "max_drawdown_proxy": _max_drawdown(returns),
            "hit_rate_by_fold": fold_rows,
            "hit_rate_by_regime": regime_rows,
            "hit_rate_by_year": year_rows,
            "turnover_proxy": float((_num_col(sub, "predicted_direction").astype(int) != 0).mean()) if len(sub) else 0.0,
            "average_holding_horizon": holding,
            "worst_fold_accuracy": worst_fold,
            "worst_regime_accuracy": worst_regime,
            "worst_year_accuracy": worst_year,
        }
    )


def _contribution(rows: list[dict[str, Any]], key: str) -> list[dict[str, Any]]:
    total = sum(_safe_int(row.get("sample_count")) for row in rows)
    out = []
    for row in rows:
        item = dict(row)
        item["contribution"] = _safe_int(row.get("sample_count")) / max(total, 1)
        out.append(item)
    return out


def _integrity_checks(frame: pd.DataFrame, wf: Mapping[str, Any], manifest: Mapping[str, Any], horizon: str) -> dict[str, Any]:
    checks: dict[str, Any] = {}
    checks["fold_id_non_empty"] = bool(not frame.empty and frame.get("fold_id") is not None and frame["fold_id"].notna().all())
    checks["sample_data_used"] = bool(manifest.get("sample_data_used", False))
    checks["baseline_used"] = bool(manifest.get("baseline_used", False))
    checks["no_duplicate_timestamp_horizon_fold"] = bool(not frame.duplicated(subset=[col for col in ["timestamp", "horizon", "fold_id"] if col in frame.columns]).any()) if not frame.empty else False
    forbidden_columns = [col for col in frame.columns if str(col).startswith(("ret_", "direction_", "tb_", "abs_ret_", "max_favorable_excursion_", "max_adverse_excursion_"))]
    checks["no_future_feature_columns_in_trace"] = len(forbidden_columns) == 0
    checks["forbidden_columns"] = forbidden_columns

    fold_windows: dict[str, Mapping[str, Any]] = {}
    for fold in wf.get("folds") or []:
        if isinstance(fold, Mapping):
            fold_windows[str(fold.get("fold"))] = fold
    label_start = pd.to_datetime(frame.get("label_start_time"), errors="coerce") if not frame.empty else pd.Series(dtype="datetime64[ns]")
    timestamp = pd.to_datetime(frame.get("timestamp"), errors="coerce") if not frame.empty else pd.Series(dtype="datetime64[ns]")
    checks["prediction_time_not_after_label_start"] = bool((timestamp <= label_start).fillna(True).all()) if not frame.empty else False
    validation_ok = True
    train_overlap_ok = True
    purge_embargo_recorded = True
    for fold_id, group in frame.groupby(frame.get("fold_id", pd.Series(dtype=str)).astype(str), observed=True):
        meta = fold_windows.get(str(fold_id))
        if not meta:
            validation_ok = False
            continue
        group_start = pd.to_datetime(group["label_start_time"], errors="coerce")
        validation_start = pd.to_datetime(meta.get("validation_start"), errors="coerce")
        validation_end = pd.to_datetime(meta.get("validation_end"), errors="coerce")
        train_end = pd.to_datetime(meta.get("train_end"), errors="coerce")
        validation_ok = validation_ok and bool(((group_start >= validation_start) & (group_start <= validation_end)).fillna(False).all())
        train_overlap_ok = train_overlap_ok and bool((group_start > train_end).fillna(False).all())
        purge_embargo_recorded = purge_embargo_recorded and _safe_int(meta.get("embargo_samples")) > 0 and "purged_samples" in meta
    checks["records_match_validation_fold"] = validation_ok
    checks["timestamp_not_in_train_window"] = train_overlap_ok
    checks["purge_embargo_recorded"] = purge_embargo_recorded
    checks["label_window_leakage_guard_recorded"] = purge_embargo_recorded
    checks["horizon"] = horizon
    return checks


def _preview_stats(frame: pd.DataFrame) -> dict[str, Any]:
    subsets = {f"top_{int(level * 100)}pct": _subset(frame, level) for level in CONFIDENCE_LEVELS}
    returns_by_subset = {name: _strategy_returns(subset).tolist() for name, subset in subsets.items()}
    all_returns = np.asarray([value for values in returns_by_subset.values() for value in values], dtype=float)
    return sanitize_for_json(
        {
            "dsr_preview": deflated_sharpe_ratio(all_returns, trials=max(1, len(returns_by_subset))),
            "pbo_preview": probability_of_backtest_overfitting(returns_by_subset),
            "reality_check_preview": bootstrap_reality_check(all_returns),
            "cost_stress": {
                "2x_cost": float(np.mean(all_returns - 0.0002)) if all_returns.size else None,
                "3x_cost": float(np.mean(all_returns - 0.0004)) if all_returns.size else None,
            },
            "message_zh": "该 preview 仅用于 OOF 高置信子集研究，不代表 promotion 通过。",
        }
    )


def _blocking_rules(subsets: Mapping[str, Mapping[str, Any]]) -> tuple[list[str], list[str]]:
    blocking: list[str] = []
    warnings: list[str] = []
    top10 = subsets.get("top_10pct", {})
    for name, subset in subsets.items():
        sample_count = _safe_int(subset.get("sample_count"))
        if sample_count < 80:
            warnings.append(f"{name} 样本数不足，不能宣传高命中率。")
        if _safe_float(subset.get("cost_adjusted_expectancy"), -1.0) <= 0:
            blocking.append(f"{name} 成本后期望不为正。")
        if abs(_safe_float(subset.get("max_drawdown_proxy"), 0.0)) > MAX_DRAWDOWN_ABS:
            blocking.append(f"{name} 最大回撤超过阈值。")
        worst_fold = subset.get("worst_fold_accuracy")
        if worst_fold is not None and _safe_float(worst_fold, 0.0) < 0.52:
            blocking.append(f"{name} 最差 fold 命中率低于 0.52。")
        for row in subset.get("hit_rate_by_regime") or []:
            if _safe_float(row.get("contribution"), 0.0) > 0.50:
                blocking.append(f"{name} 单一 regime 贡献超过 50%。")
                break
        for row in subset.get("hit_rate_by_year") or []:
            if _safe_float(row.get("contribution"), 0.0) > 0.35:
                blocking.append(f"{name} 单一年份贡献超过 35%。")
                break
    for row in top10.get("hit_rate_by_fold") or []:
        if _safe_float(row.get("contribution"), 0.0) > 0.45:
            blocking.append("top_10pct 单一 fold 贡献超过 45%。")
            break
    return list(dict.fromkeys(blocking)), list(dict.fromkeys(warnings))


def _horizon_report(horizon: str, manifest: Mapping[str, Any], candidate_version: str = "v1") -> dict[str, Any]:
    frame = _read_trace(horizon, candidate_version=candidate_version)
    wf = _load_wf(horizon, candidate_version=candidate_version)
    checks = _integrity_checks(frame, wf, manifest, horizon)
    subset_metrics = {}
    for level in CONFIDENCE_LEVELS:
        key = f"top_{int(level * 100)}pct"
        metrics = _subset_metrics(frame, level)
        metrics["hit_rate_by_fold"] = _contribution(metrics.get("hit_rate_by_fold", []), "fold_id")
        metrics["hit_rate_by_regime"] = _contribution(metrics.get("hit_rate_by_regime", []), "regime_label")
        metrics["hit_rate_by_year"] = _contribution(metrics.get("hit_rate_by_year", []), "year")
        subset_metrics[key] = metrics
    blocking, warnings = _blocking_rules(subset_metrics)
    integrity_failures = [key for key, value in checks.items() if key not in {"forbidden_columns", "horizon", "sample_data_used", "baseline_used"} and value is False]
    if checks.get("sample_data_used"):
        integrity_failures.append("sample_data_used")
    if checks.get("baseline_used"):
        integrity_failures.append("baseline_used")
    blocking.extend([f"完整性检查失败：{item}" for item in integrity_failures])
    fold_rows = _contribution(_hit_by_group(frame, "fold_id"), "fold_id")
    regime_rows = _contribution(_hit_by_group(frame, "regime_label"), "regime_label")
    year_rows = _contribution(_year_rows(frame), "year")
    report = {
        "trace_rows": int(len(frame)),
        "fold_count": int(frame["fold_id"].nunique()) if not frame.empty and "fold_id" in frame.columns else 0,
        "leakage_checks": checks,
        "fold_contribution": fold_rows,
        "time_period_contribution": year_rows,
        "regime_contribution": regime_rows,
        "confidence_subset": subset_metrics,
        "cost_adjusted_metrics": {key: value.get("cost_adjusted_expectancy") for key, value in subset_metrics.items()},
        "drawdown_metrics": {key: value.get("max_drawdown_proxy") for key, value in subset_metrics.items()},
        "preview": _preview_stats(frame),
        "integrity_pass": not integrity_failures,
        "blocking_reasons": list(dict.fromkeys(blocking)),
        "warnings": warnings,
    }
    return sanitize_for_json(report)


def build_oof_integrity_report(candidate_version: str = "v1", dataset_version: str | None = None) -> dict[str, Any]:
    candidate_version = _normalise_version(candidate_version)
    dataset_version = _normalise_version(dataset_version or candidate_version)
    manifest = _load_manifest(dataset_version)
    horizons = {horizon: _horizon_report(horizon, manifest, candidate_version=candidate_version) for horizon in DEFAULT_HORIZONS}
    all_blocking = [reason for payload in horizons.values() for reason in payload.get("blocking_reasons", [])]
    all_warnings = [reason for payload in horizons.values() for reason in payload.get("warnings", [])]
    has_trace = any(int(payload.get("trace_rows") or 0) > 0 for payload in horizons.values())
    if all_blocking:
        readiness = "reject"
    elif has_trace and all_warnings:
        readiness = "research_only"
    elif has_trace:
        readiness = "eligible_for_next_candidate"
    else:
        readiness = "research_only"
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_version": candidate_version,
        "dataset_version": dataset_version,
        "horizons": horizons,
        "global_summary": {
            "trace_available": has_trace,
            "blocking_reason_count": len(all_blocking),
            "warning_count": len(all_warnings),
            "message_zh": "OOF 完整性和高置信稳健性审计只用于研究，不发布 active，不生成客户预测。",
        },
        "promotion_readiness": readiness,
        "active_updated": False,
        "customer_prediction_generated": False,
        "promotion_gate_lowered": False,
    }
    _report_path(candidate_version).write_text(json.dumps(sanitize_for_json(report), ensure_ascii=False, indent=2), encoding="utf-8")
    return sanitize_for_json(report)


def get_oof_integrity_report(candidate_version: str = "v1", dataset_version: str | None = None) -> dict[str, Any]:
    candidate_version = _normalise_version(candidate_version)
    if _report_path(candidate_version).exists():
        payload = _read_json(_report_path(candidate_version))
        if isinstance(payload, Mapping):
            return sanitize_for_json(payload)
    return build_oof_integrity_report(candidate_version=candidate_version, dataset_version=dataset_version)


def get_high_confidence_report(horizon: str = "1d", candidate_version: str = "v1", dataset_version: str | None = None) -> dict[str, Any]:
    report = get_oof_integrity_report(candidate_version=candidate_version, dataset_version=dataset_version)
    payload = (report.get("horizons") or {}).get(str(horizon))
    if not isinstance(payload, Mapping):
        return sanitize_for_json(
            {
                "status": "not_found",
                "horizon": str(horizon),
                "message_zh": "未找到该周期的高置信 OOF 报告。",
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    return sanitize_for_json(
        {
            "status": "success",
            "horizon": str(horizon),
            "confidence_subset": payload.get("confidence_subset", {}),
            "blocking_reasons": payload.get("blocking_reasons", []),
            "warnings": payload.get("warnings", []),
            "preview": payload.get("preview", {}),
            "message_zh": "高置信 OOF 命中率不是客户预测，不代表未来收益，不构成投资建议。",
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )
