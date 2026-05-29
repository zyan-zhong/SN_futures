from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


OOF_TRACE_COLUMNS = [
    "candidate_version",
    "dataset_version",
    "feature_set",
    "horizon",
    "fold_id",
    "timestamp",
    "label_start_time",
    "label_end_time",
    "close",
    "realized_direction",
    "realized_return",
    "realized_vol",
    "raw_prob_up",
    "calibrated_prob_up",
    "predicted_direction",
    "expected_return",
    "confidence",
    "trade_edge",
    "selected_signal",
    "no_trade_reason",
    "regime_label",
    "regime_volatility_score",
    "regime_trend_score",
    "event_shock_score",
    "usd_cny",
    "us10y",
    "copper_global_proxy",
    "data_quality_score",
    "feature_coverage_score",
    "model_family",
    "model_id",
    "calibration_method",
    "cost_assumption",
    "sample_weight",
    "is_high_confidence_top_10",
    "is_high_confidence_top_20",
    "error_type",
    "drawdown_contribution",
]


def _output_dir() -> Path:
    return get_user_output_dir()


def _walk_forward_dir() -> Path:
    path = _output_dir() / "walk_forward"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _research_dir(experiment_id: str) -> Path:
    safe_id = Path(str(experiment_id)).name
    path = _output_dir() / "model_research" / "experiments" / safe_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalise_version(version: str | None) -> str:
    value = str(version or "v1").strip().lower()
    return value or "v1"


def _walk_forward_trace_path(horizon: str, candidate_version: str | None = "v1") -> Path:
    version = _normalise_version(candidate_version)
    base = _walk_forward_dir() if version == "v1" else _walk_forward_dir() / version
    base.mkdir(parents=True, exist_ok=True)
    return base / f"oof_trace_{horizon}.csv"


def _research_trace_path(experiment_id: str, horizon: str) -> Path:
    return _research_dir(experiment_id) / f"oof_trace_{horizon}.csv"


def _safe_float(value: Any, default: float | None = None) -> float | None:
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


def _format_time(value: Any) -> str:
    if value is None:
        return ""
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return str(value)
        return parsed.isoformat()
    except Exception:
        return str(value)


def _direction_from_prob(prob_up: float, expected_return: float) -> int:
    if prob_up > 0.55 and expected_return > 0:
        return 1
    if prob_up < 0.45 and expected_return < 0:
        return -1
    return 0


def _signal_from_direction(direction: int) -> tuple[str, str]:
    if direction > 0:
        return "多头研究观察", ""
    if direction < 0:
        return "空头研究观察", ""
    return "观望", "概率或收益边际不足"


def build_oof_trace_records(
    *,
    horizon: str,
    fold_id: Any,
    validation: pd.DataFrame,
    raw_prob_up: Iterable[Any],
    calibrated_prob_up: Iterable[Any],
    expected_return: Iterable[Any],
    model_family: str,
    model_id: str,
    calibration_method: str,
    cost_assumption: float,
    data_quality_score: float | None = None,
    feature_coverage_score: float | None = None,
    candidate_version: str = "v1",
    dataset_version: str = "v1",
    feature_set: str = "",
) -> list[dict[str, Any]]:
    raw = np.asarray([_safe_float(value, 0.5) for value in raw_prob_up], dtype=float)
    calibrated = np.asarray([_safe_float(value, 0.5) for value in calibrated_prob_up], dtype=float)
    expected = np.asarray([_safe_float(value, 0.0) for value in expected_return], dtype=float)
    n = min(len(validation), raw.size, calibrated.size, expected.size)
    if n <= 0:
        return []
    frame = validation.iloc[:n].copy().reset_index(drop=True)
    confidence = np.abs(calibrated[:n] - 0.5) * 2.0
    top10_cut = float(np.quantile(confidence, 0.90)) if n >= 2 else float(confidence[0])
    top20_cut = float(np.quantile(confidence, 0.80)) if n >= 2 else float(confidence[0])
    returns = pd.to_numeric(frame.get("y_return", pd.Series([0.0] * n)), errors="coerce").fillna(0.0).to_numpy(dtype=float)

    records: list[dict[str, Any]] = []
    for idx in range(n):
        realized_direction = _safe_int(frame.get("y_direction", pd.Series([0] * n)).iloc[idx], 0)
        expected_value = float(expected[idx])
        calibrated_value = float(calibrated[idx])
        predicted_direction = _direction_from_prob(calibrated_value, expected_value)
        selected_signal, no_trade_reason = _signal_from_direction(predicted_direction)
        trade_edge = abs(expected_value) - float(cost_assumption)
        strategy_return = (np.sign(predicted_direction) * returns[idx] - float(cost_assumption)) if predicted_direction != 0 else 0.0
        wrong = predicted_direction != 0 and realized_direction != 0 and int(np.sign(predicted_direction)) != int(np.sign(realized_direction))
        record = {
            "candidate_version": candidate_version,
            "dataset_version": dataset_version,
            "feature_set": feature_set,
            "horizon": str(horizon),
            "fold_id": str(fold_id),
            "timestamp": _format_time(frame.get("timestamp", frame.get("label_start_time", pd.Series([""] * n))).iloc[idx]),
            "label_start_time": _format_time(frame.get("label_start_time", pd.Series([""] * n)).iloc[idx]),
            "label_end_time": _format_time(frame.get("label_end_time", pd.Series([""] * n)).iloc[idx]),
            "close": _safe_float(frame.get("close", pd.Series([None] * n)).iloc[idx]),
            "realized_direction": realized_direction,
            "realized_return": float(returns[idx]),
            "realized_vol": _safe_float(frame.get("realized_vol", frame.get("atr_14", pd.Series([None] * n))).iloc[idx]),
            "raw_prob_up": float(raw[idx]),
            "calibrated_prob_up": calibrated_value,
            "predicted_direction": int(predicted_direction),
            "expected_return": expected_value,
            "confidence": float(confidence[idx]),
            "trade_edge": float(trade_edge),
            "selected_signal": selected_signal,
            "no_trade_reason": no_trade_reason,
            "regime_label": str(frame.get("regime_label", pd.Series(["UNKNOWN"] * n)).iloc[idx] or "UNKNOWN"),
            "regime_volatility_score": _safe_float(frame.get("regime_volatility_score", pd.Series([None] * n)).iloc[idx]),
            "regime_trend_score": _safe_float(frame.get("regime_trend_score", pd.Series([None] * n)).iloc[idx]),
            "event_shock_score": _safe_float(frame.get("event_shock_score", frame.get("news_event_score", pd.Series([None] * n))).iloc[idx]),
            "usd_cny": _safe_float(frame.get("usd_cny", pd.Series([None] * n)).iloc[idx]),
            "us10y": _safe_float(frame.get("us10y", pd.Series([None] * n)).iloc[idx]),
            "copper_global_proxy": _safe_float(frame.get("copper_global_proxy", pd.Series([None] * n)).iloc[idx]),
            "data_quality_score": data_quality_score,
            "feature_coverage_score": feature_coverage_score,
            "model_family": model_family,
            "model_id": model_id,
            "calibration_method": calibration_method,
            "cost_assumption": float(cost_assumption),
            "sample_weight": _safe_float(frame.get("sample_weight", pd.Series([1.0] * n)).iloc[idx], 1.0),
            "is_high_confidence_top_10": bool(confidence[idx] >= top10_cut),
            "is_high_confidence_top_20": bool(confidence[idx] >= top20_cut),
            "error_type": "high_confidence_wrong" if wrong and confidence[idx] >= top20_cut else ("wrong_direction" if wrong else ""),
            "drawdown_contribution": float(min(0.0, strategy_return)),
        }
        records.append(record)
    return sanitize_for_json(records)


def write_oof_trace(
    records: Iterable[Mapping[str, Any]],
    *,
    horizon: str,
    experiment_id: str | None = None,
    candidate_version: str = "v1",
) -> dict[str, Any]:
    path = _research_trace_path(experiment_id, horizon) if experiment_id else _walk_forward_trace_path(horizon, candidate_version)
    rows = [dict(row) for row in records]
    frame = pd.DataFrame(rows)
    for column in OOF_TRACE_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    frame = frame[OOF_TRACE_COLUMNS]
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False, encoding="utf-8")
    summary = summarize_oof_trace_file(path, horizon=horizon)
    summary_path = path.with_suffix(".summary.json")
    summary_path.write_text(json.dumps(sanitize_for_json(summary), ensure_ascii=False, indent=2), encoding="utf-8")
    return sanitize_for_json({"path": str(path), "summary_path": str(summary_path), **summary})


def _read_trace(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=OOF_TRACE_COLUMNS)
    try:
        frame = pd.read_csv(path)
    except Exception:
        return pd.DataFrame(columns=OOF_TRACE_COLUMNS)
    for column in OOF_TRACE_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return frame


def _calibration_bins(frame: pd.DataFrame, bins: int = 10) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    work = frame.copy()
    work["calibrated_prob_up"] = pd.to_numeric(work["calibrated_prob_up"], errors="coerce")
    work["realized_up"] = (pd.to_numeric(work["realized_direction"], errors="coerce").fillna(0) > 0).astype(int)
    work = work.dropna(subset=["calibrated_prob_up"])
    if work.empty:
        return []
    work["bin"] = pd.cut(work["calibrated_prob_up"], bins=np.linspace(0, 1, bins + 1), include_lowest=True)
    rows: list[dict[str, Any]] = []
    for bucket, group in work.groupby("bin", observed=True):
        rows.append(
            {
                "bin": str(bucket),
                "predicted_probability_mean": float(group["calibrated_prob_up"].mean()),
                "realized_up_rate": float(group["realized_up"].mean()),
                "sample_count": int(len(group)),
                "brier_contribution": float(np.mean((group["calibrated_prob_up"] - group["realized_up"]) ** 2)),
            }
        )
    return rows


def _confidence_deciles(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    work = frame.copy()
    work["confidence"] = pd.to_numeric(work["confidence"], errors="coerce").fillna(0.0)
    work["realized_direction"] = pd.to_numeric(work["realized_direction"], errors="coerce").fillna(0).astype(int)
    work["predicted_direction"] = pd.to_numeric(work["predicted_direction"], errors="coerce").fillna(0).astype(int)
    work["realized_return"] = pd.to_numeric(work["realized_return"], errors="coerce").fillna(0.0)
    work["cost_assumption"] = pd.to_numeric(work["cost_assumption"], errors="coerce").fillna(0.0)
    if len(work) < 2:
        buckets = [("all", work)]
    else:
        work["bucket"] = pd.qcut(work["confidence"].rank(method="first"), q=min(10, len(work)), duplicates="drop")
        buckets = [(str(bucket), group) for bucket, group in work.groupby("bucket", observed=True)]
    rows: list[dict[str, Any]] = []
    for bucket, group in buckets:
        selected = group[group["predicted_direction"] != 0]
        correct = selected["predicted_direction"].to_numpy() == np.sign(selected["realized_direction"].to_numpy())
        strategy_return = np.sign(selected["predicted_direction"].to_numpy()) * selected["realized_return"].to_numpy() - selected["cost_assumption"].to_numpy()
        rows.append(
            {
                "bucket": bucket,
                "sample_count": int(len(group)),
                "coverage": float(len(group) / max(len(work), 1)),
                "signal_count": int(len(selected)),
                "accuracy": float(correct.mean()) if len(correct) else None,
                "cost_adjusted_expectancy": float(strategy_return.mean()) if len(strategy_return) else None,
                "average_confidence": float(group["confidence"].mean()) if len(group) else None,
            }
        )
    rows.sort(key=lambda item: str(item["bucket"]), reverse=True)
    return sanitize_for_json(rows)


def _top_confidence_metrics(frame: pd.DataFrame, pct: float) -> dict[str, Any]:
    if frame.empty:
        return {"coverage": pct, "sample_count": 0, "accuracy": None, "cost_adjusted_expectancy": None}
    work = frame.copy()
    work["confidence"] = pd.to_numeric(work["confidence"], errors="coerce").fillna(0.0)
    cutoff = work["confidence"].quantile(max(0.0, min(1.0, 1.0 - pct)))
    subset = work[work["confidence"] >= cutoff]
    selected = subset[pd.to_numeric(subset["predicted_direction"], errors="coerce").fillna(0).astype(int) != 0]
    pred = pd.to_numeric(selected["predicted_direction"], errors="coerce").fillna(0).astype(int).to_numpy()
    realized = np.sign(pd.to_numeric(selected["realized_direction"], errors="coerce").fillna(0).astype(int).to_numpy())
    correct = pred == realized
    returns = pd.to_numeric(selected["realized_return"], errors="coerce").fillna(0.0).to_numpy()
    costs = pd.to_numeric(selected["cost_assumption"], errors="coerce").fillna(0.0).to_numpy()
    strategy_return = np.sign(pred) * returns - costs
    return {
        "coverage": pct,
        "sample_count": int(len(subset)),
        "signal_count": int(len(selected)),
        "accuracy": float(correct.mean()) if len(correct) else None,
        "cost_adjusted_expectancy": float(strategy_return.mean()) if len(strategy_return) else None,
    }


def _confusion_matrix(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"labels": [-1, 0, 1], "matrix": [[0, 0, 0], [0, 0, 0], [0, 0, 0]]}
    labels = [-1, 0, 1]
    actual = pd.to_numeric(frame["realized_direction"], errors="coerce").fillna(0).astype(int).map(lambda v: int(np.sign(v)))
    pred = pd.to_numeric(frame["predicted_direction"], errors="coerce").fillna(0).astype(int).map(lambda v: int(np.sign(v)))
    matrix = []
    for a in labels:
        matrix.append([int(((actual == a) & (pred == p)).sum()) for p in labels])
    return {"labels": labels, "matrix": matrix}


def _regime_errors(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty or "regime_label" not in frame.columns:
        return []
    work = frame.copy()
    work["predicted_direction"] = pd.to_numeric(work["predicted_direction"], errors="coerce").fillna(0).astype(int)
    work["realized_direction"] = pd.to_numeric(work["realized_direction"], errors="coerce").fillna(0).astype(int)
    rows: list[dict[str, Any]] = []
    for regime, group in work.groupby(work["regime_label"].fillna("UNKNOWN").astype(str), observed=True):
        selected = group[group["predicted_direction"] != 0]
        wrong = selected[np.sign(selected["predicted_direction"]) != np.sign(selected["realized_direction"])]
        rows.append(
            {
                "regime_label": regime,
                "sample_count": int(len(group)),
                "signal_count": int(len(selected)),
                "error_count": int(len(wrong)),
                "error_rate": float(len(wrong) / max(len(selected), 1)) if len(selected) else None,
            }
        )
    return sorted(rows, key=lambda item: item["error_count"], reverse=True)


def _sample_rows(frame: pd.DataFrame, *, limit: int, high_conf_wrong: bool = False, drawdown: bool = False) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    work = frame.copy()
    if high_conf_wrong and "error_type" in work.columns:
        work = work[work["error_type"].fillna("").astype(str).str.contains("wrong")]
    if drawdown:
        work["drawdown_contribution"] = pd.to_numeric(work["drawdown_contribution"], errors="coerce").fillna(0.0)
        work = work.sort_values("drawdown_contribution")
    else:
        work["confidence"] = pd.to_numeric(work["confidence"], errors="coerce").fillna(0.0)
        work = work.sort_values("confidence", ascending=False)
    return sanitize_for_json(work.head(limit).to_dict(orient="records"))


def summarize_oof_trace_file(path: Path, *, horizon: str | None = None) -> dict[str, Any]:
    frame = _read_trace(path)
    h = horizon or (str(frame["horizon"].dropna().iloc[0]) if not frame.empty and frame["horizon"].notna().any() else "")
    return sanitize_for_json(
        {
            "status": "success" if not frame.empty else "empty",
            "horizon": h,
            "path": str(path),
            "row_count": int(len(frame)),
            "fold_count": int(frame["fold_id"].nunique()) if not frame.empty else 0,
            "date_start": str(frame["label_start_time"].dropna().min()) if not frame.empty else "",
            "date_end": str(frame["label_end_time"].dropna().max()) if not frame.empty else "",
            "confusion_matrix": _confusion_matrix(frame),
            "calibration_bins": _calibration_bins(frame),
            "confidence_deciles": _confidence_deciles(frame),
            "top_10pct": _top_confidence_metrics(frame, 0.10),
            "top_20pct": _top_confidence_metrics(frame, 0.20),
            "regime_error_hotspots": _regime_errors(frame),
            "high_confidence_wrong_samples": _sample_rows(frame, limit=20, high_conf_wrong=True),
            "drawdown_contribution_samples": _sample_rows(frame, limit=20, drawdown=True),
            "message_zh": "OOF trace 是 walk-forward 验证样本外轨迹，仅用于研究诊断，不是客户预测。",
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def get_oof_trace_summary(horizon: str = "1d", candidate_version: str = "v1") -> dict[str, Any]:
    path = _walk_forward_trace_path(str(horizon), candidate_version)
    if not path.exists():
        return sanitize_for_json(
            {
                "status": "not_found",
                "horizon": str(horizon),
                "path": str(path),
                "row_count": 0,
                "message_zh": "尚未找到该周期的 OOF 样本外验证轨迹，请先运行 candidate walk-forward。",
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    return summarize_oof_trace_file(path, horizon=str(horizon))


def get_oof_trace_sample(horizon: str = "1d", limit: int = 200, candidate_version: str = "v1") -> dict[str, Any]:
    path = _walk_forward_trace_path(str(horizon), candidate_version)
    frame = _read_trace(path)
    safe_limit = max(1, min(int(limit), 1000))
    return sanitize_for_json(
        {
            "status": "success" if not frame.empty else "empty",
            "horizon": str(horizon),
            "path": str(path),
            "rows": _sample_rows(frame, limit=safe_limit),
            "limit": safe_limit,
            "message_zh": "样本仅为 OOF 验证轨迹截取，不是客户预测。",
        }
    )


def get_research_oof_trace_summary(experiment_id: str) -> dict[str, Any]:
    safe_id = Path(str(experiment_id)).name
    path = _research_dir(safe_id)
    traces = sorted(path.glob("oof_trace_*.csv"))
    if not safe_id or not traces:
        return sanitize_for_json(
            {
                "status": "not_found",
                "experiment_id": experiment_id,
                "message_zh": "尚未找到该研究实验的 OOF trace。",
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    summaries = {}
    for trace in traces:
        horizon = trace.stem.replace("oof_trace_", "")
        summaries[horizon] = summarize_oof_trace_file(trace, horizon=horizon)
    return sanitize_for_json(
        {
            "status": "success",
            "experiment_id": safe_id,
            "summaries": summaries,
            "message_zh": "研究实验 OOF trace 仅用于样本外诊断，不是客户预测。",
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def trace_inventory() -> dict[str, Any]:
    rows = []
    for path in sorted(_walk_forward_dir().glob("oof_trace_*.csv")):
        rows.append(summarize_oof_trace_file(path, horizon=path.stem.replace("oof_trace_", "")))
    return sanitize_for_json({"generated_at": datetime.now().isoformat(timespec="seconds"), "traces": rows})
