from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .candidate_v7_research_service import DEFAULT_HORIZONS, _horizon_days, _normalise_horizons, _v7_feature_evidence
from .feature_stability_evidence_service import build_feature_stability_evidence
from .feature_store_service import get_feature_store_status
from .feature_store_v7_service import build_feature_store_v7, build_training_dataset_v7
from .institutional_validation_service import run_institutional_validation
from .model_promotion_service import promote_candidate
from .oof_integrity_service import get_oof_integrity_report
from .research_artifact_service import archive_research_run
from .research_backtest_service import run_research_backtest
from .stable_strategy_policy_service import build_stable_strategy_policy
from .training_dataset_service import get_training_dataset_status
from .walk_forward_training_service import run_candidate_training


V8_CANDIDATE_VERSION = "v8"
V8_FEATURE_STORE_VERSION = "v7"
V8_DATASET_VERSION = "v7"
V8_RESEARCH_FEATURE_SET = "tushare_cost_positioning_stable"
V8_LABEL_VARIANTS = (
    "direction_thresholded",
    "volatility_adjusted_direction",
    "triple_barrier_atr",
    "meta_label_tradeability",
)
V8_CALIBRATION = ("sigmoid",)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _research_dir() -> Path:
    path = _output_dir() / "model_research" / "candidate_v8"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_path() -> Path:
    return _research_dir() / "candidate_v8_gated_research_report.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _manifest_sample_or_mock(payload: Mapping[str, Any]) -> bool:
    return bool(payload.get("sample_data_used") or payload.get("mock_data_used") or payload.get("baseline_used"))


def _admission(feature_store: Mapping[str, Any], dataset: Mapping[str, Any]) -> dict[str, Any]:
    blocked: list[str] = []
    if not feature_store or feature_store.get("status") != "success":
        blocked.append("feature_store_v7_missing")
    if feature_store and str(feature_store.get("version") or "").lower() != "v7":
        blocked.append("feature_store_v7_missing")
    if feature_store and not bool(feature_store.get("leakage_check_pass", True)):
        blocked.append("feature_store_v7_leakage_failed")
    if feature_store and not bool(feature_store.get("no_lookahead_pass", True)):
        blocked.append("feature_store_v7_no_lookahead_failed")
    if feature_store and _manifest_sample_or_mock(feature_store):
        blocked.append("feature_store_v7_sample_or_mock_detected")
    if not dataset or dataset.get("status") != "success":
        blocked.append("training_dataset_v7_missing")
    if dataset and not bool(dataset.get("leakage_check_pass")):
        blocked.append("training_dataset_v7_leakage_failed")
    if dataset and not bool(dataset.get("no_lookahead_pass", True)):
        blocked.append("training_dataset_v7_no_lookahead_failed")
    if dataset and _manifest_sample_or_mock(dataset):
        blocked.append("training_dataset_v7_sample_or_mock_detected")
    evidence = _v7_feature_evidence(feature_store, dataset)
    if not evidence["cost_features"]:
        blocked.append("v7_cost_features_missing")
    if not evidence["positioning_features"]:
        blocked.append("v7_positioning_features_missing")
    return {
        "eligible": not blocked,
        "stage": "candidate_v8_admission",
        "candidate_version": "v8",
        "feature_store_version": "v7",
        "dataset_version": "v7",
        "blocked_reasons": sorted(set(blocked)),
        "v7_feature_evidence": evidence,
    }


def _blocked_result(admission: Mapping[str, Any], *, horizons: tuple[str, ...], feature_store: Mapping[str, Any], dataset: Mapping[str, Any]) -> dict[str, Any]:
    report = {
        "status": "blocked",
        "generated_at": _now(),
        "report_path": str(_report_path()),
        "candidate_version": "v8",
        "dataset_version": V8_DATASET_VERSION,
        "feature_store_version": V8_FEATURE_STORE_VERSION,
        "feature_set": V8_RESEARCH_FEATURE_SET,
        "horizons": horizons,
        "v8_admission": dict(admission),
        "v7_feature_evidence": dict(admission.get("v7_feature_evidence") or {}),
        "feature_store_v7": dict(feature_store),
        "training_dataset_v7": dict(dataset),
        "blocked_reasons": list(admission.get("blocked_reasons") or []),
        "blocking_reasons": list(admission.get("blocked_reasons") or []),
        "candidate": {"status": "not_run"},
        "research_backtest": {"status": "not_run"},
        "institutional_validation": {"status": "not_run"},
        "promotion_dry_run": {"status": "not_run"},
        "stable_strategy_policy": {"status": "not_run"},
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "promotion_gate_lowered": False,
        "manual_approval_recommended": False,
    }
    _write_json(_report_path(), report)
    return sanitize_for_json(report)


def _copy_payload_to_research(name: str, payload: Mapping[str, Any]) -> str:
    path = _research_dir() / name
    _write_json(path, payload)
    return str(path)


def _copy_file_to_research(source: Any, name: str) -> str:
    src = Path(str(source or ""))
    target = _research_dir() / name
    if src.exists():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
    else:
        _write_json(target, {"status": "missing_source", "source": str(source or "")})
    return str(target)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _nested(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _horizon_metrics_from_artifacts(horizons: Iterable[str]) -> dict[str, dict[str, Any]]:
    v7_status = _read_json(_output_dir() / "model_registry" / "candidate_v7_training_status.json") or {}
    metrics_by_horizon = v7_status.get("metrics_by_horizon") if isinstance(v7_status, Mapping) else {}
    rows: dict[str, dict[str, Any]] = {}
    for horizon in horizons:
        h = str(horizon)
        metrics = dict(metrics_by_horizon.get(h) or {}) if isinstance(metrics_by_horizon, Mapping) else {}
        backtest_metrics = _read_json(_output_dir() / "research_backtests" / "v7" / f"metrics_{h}.json") or {}
        if isinstance(backtest_metrics, Mapping):
            metrics.setdefault("turnover", backtest_metrics.get("turnover"))
            metrics.setdefault("trade_count", backtest_metrics.get("trade_count"))
            metrics.setdefault("max_drawdown", backtest_metrics.get("max_drawdown"))
            metrics.setdefault("expectancy", backtest_metrics.get("expectancy"))
            stress = backtest_metrics.get("cost_stress") if isinstance(backtest_metrics.get("cost_stress"), Mapping) else {}
            two_x = _nested(stress, "2x_cost", "expectancy")
            three_x = _nested(stress, "3x_cost", "expectancy")
            metrics.setdefault("cost_adjusted_expectancy", min(_safe_float(two_x, 0.0), _safe_float(three_x, 0.0)))
        rows[h] = metrics
    return rows


def _metric_summary(validation: Mapping[str, Any], backtest: Mapping[str, Any]) -> dict[str, Any]:
    horizons = backtest.get("horizons") if isinstance(backtest.get("horizons"), Mapping) else {}
    metrics_rows = [
        payload.get("metrics")
        for payload in horizons.values()
        if isinstance(payload, Mapping) and isinstance(payload.get("metrics"), Mapping)
    ]
    trade_count = sum(int(_safe_float(item.get("trade_count"), 0)) for item in metrics_rows)
    turnover = sum(_safe_float(item.get("turnover"), 0.0) for item in metrics_rows) / max(len(metrics_rows), 1)
    max_drawdown = min((_safe_float(item.get("max_drawdown"), 0.0) for item in metrics_rows), default=0.0)
    two_x_values = [_safe_float(_nested(item, "cost_stress", "2x_cost", "expectancy"), 0.0) for item in metrics_rows]
    three_x_values = [_safe_float(_nested(item, "cost_stress", "3x_cost", "expectancy"), 0.0) for item in metrics_rows]
    return {
        "PBO": _safe_float(_nested(validation, "probability_of_backtest_overfitting", "pbo"), _safe_float(validation.get("pbo"), 0.0)),
        "DSR": _safe_float(_nested(validation, "deflated_sharpe_ratio", "deflated_sharpe_ratio"), _safe_float(validation.get("dsr"), 0.0)),
        "Reality Check p-value": _safe_float(_nested(validation, "reality_check", "p_value"), _safe_float(validation.get("reality_check_p_value"), 1.0)),
        "2x cost expectancy": sum(two_x_values) / max(len(two_x_values), 1),
        "3x cost expectancy": sum(three_x_values) / max(len(three_x_values), 1),
        "max_drawdown": max_drawdown,
        "turnover": turnover,
        "trade_count": trade_count,
    }


def _previous_v7_summary() -> dict[str, Any]:
    validation = _read_json(_output_dir() / "institutional_validation" / "institutional_validation_report_v7.json") or {}
    horizons: dict[str, Any] = {}
    for path in sorted((_output_dir() / "research_backtests" / "v7").glob("metrics_*.json")):
        h = path.stem.replace("metrics_", "")
        metrics = _read_json(path) or {}
        horizons[h] = {"metrics": metrics}
    return _metric_summary(validation if isinstance(validation, Mapping) else {}, {"horizons": horizons})


def _compare(v8_validation: Mapping[str, Any], v8_backtest: Mapping[str, Any]) -> dict[str, Any]:
    before = _previous_v7_summary()
    after = _metric_summary(v8_validation, v8_backtest)
    return {
        "v7": before,
        "v8": after,
        "improvement": {
            "PBO": before.get("PBO", 0.0) - after.get("PBO", 0.0),
            "DSR": after.get("DSR", 0.0) - before.get("DSR", 0.0),
            "Reality Check p-value": before.get("Reality Check p-value", 1.0) - after.get("Reality Check p-value", 1.0),
            "max_drawdown_abs": abs(_safe_float(before.get("max_drawdown"), 0.0)) - abs(_safe_float(after.get("max_drawdown"), 0.0)),
            "turnover": before.get("turnover", 0.0) - after.get("turnover", 0.0),
            "trade_count": before.get("trade_count", 0) - after.get("trade_count", 0),
        },
    }


def _trace_path(candidate_version: str, horizon: str) -> Path:
    return _output_dir() / "walk_forward" / str(candidate_version) / f"oof_trace_{horizon}.csv"


def _wf_path(candidate_version: str, horizon: str) -> Path:
    return _output_dir() / "walk_forward" / str(candidate_version) / f"wf_{horizon}.json"


def _candidate_status_path(candidate_version: str) -> Path:
    return _output_dir() / "model_registry" / f"candidate_{candidate_version}_training_status.json"


def _candidate_registry_path(candidate_version: str) -> Path:
    return _output_dir() / "model_registry" / f"candidate_{candidate_version}_model_registry.json"


def _policy_for_horizon(stable_policy: Mapping[str, Any], horizon: str) -> Mapping[str, Any]:
    policies = stable_policy.get("horizon_policy") if isinstance(stable_policy.get("horizon_policy"), Mapping) else {}
    value = policies.get(str(horizon)) if isinstance(policies, Mapping) else None
    if isinstance(value, Mapping):
        return value
    thresholds = stable_policy.get("threshold_policy") if isinstance(stable_policy.get("threshold_policy"), Mapping) else {}
    return {
        "trade_enabled": True,
        "min_confidence": thresholds.get("min_confidence", 0.62),
        "min_trade_edge": thresholds.get("min_trade_edge", 0.0003),
        "max_trade_rate": thresholds.get("max_trade_rate", 0.15),
        "reasons": [],
    }


def _apply_policy_frame(frame: pd.DataFrame, horizon: str, policy: Mapping[str, Any]) -> tuple[pd.DataFrame, dict[str, Any]]:
    work = frame.copy()
    if work.empty:
        return work, {"status": "empty", "horizon": horizon}
    confidence = pd.to_numeric(work.get("confidence", 0.0), errors="coerce").fillna(0.0).astype(float)
    edge = pd.to_numeric(work.get("trade_edge", 0.0), errors="coerce").fillna(0.0).astype(float)
    predicted = pd.to_numeric(work.get("predicted_direction", 0), errors="coerce").fillna(0).astype(int)
    trade_enabled = bool(policy.get("trade_enabled", True))
    min_confidence = _safe_float(policy.get("min_confidence"), 0.62)
    min_edge = _safe_float(policy.get("min_trade_edge"), 0.0003)
    max_trade_rate = max(0.0, min(1.0, _safe_float(policy.get("max_trade_rate"), 0.15)))
    selected = (predicted != 0) & (edge >= min_edge) & (confidence >= min_confidence) if trade_enabled else pd.Series(False, index=work.index)
    if trade_enabled and selected.any():
        max_count = max(1, int(np.floor(len(work) * max_trade_rate)))
        score = (confidence.abs() * edge.abs()).where(selected, -np.inf)
        keep_index = set(score.nlargest(max_count).index.tolist())
        selected = selected & pd.Series(work.index.isin(keep_index), index=work.index)
    reason = "stable_policy_selected"
    if not trade_enabled:
        reason = "stable_policy_disabled_horizon"
    work["stable_policy_selected"] = selected.astype(bool)
    work["stable_policy_reason"] = np.where(selected, "selected", reason)
    work.loc[~selected, "predicted_direction"] = 0
    work.loc[~selected, "trade_edge"] = 0.0
    if "expected_return" in work.columns:
        work.loc[~selected, "expected_return"] = 0.0
    work["selected_signal"] = np.where(selected, "stable_selected", "stable_no_trade")
    work["no_trade_reason"] = np.where(selected, "", work.get("no_trade_reason", "stable_policy_threshold"))
    metrics = _policy_metrics(work, horizon)
    metrics["stable_policy"] = {
        "trade_enabled": trade_enabled,
        "min_confidence": min_confidence,
        "min_trade_edge": min_edge,
        "max_trade_rate": max_trade_rate,
        "selected_count": int(selected.sum()),
        "selected_rate": float(selected.mean()) if len(selected) else 0.0,
    }
    return work, metrics


def _policy_metrics(frame: pd.DataFrame, horizon: str) -> dict[str, Any]:
    selected = frame.get("stable_policy_selected")
    if selected is None:
        selected = pd.Series(False, index=frame.index)
    selected = selected.astype(bool)
    realized_direction = pd.to_numeric(frame.get("realized_direction", 0), errors="coerce").fillna(0).astype(int)
    realized_return = pd.to_numeric(frame.get("realized_return", 0.0), errors="coerce").fillna(0.0).astype(float)
    predicted = pd.to_numeric(frame.get("predicted_direction", 0), errors="coerce").fillna(0).astype(int)
    cost = pd.to_numeric(frame.get("cost_assumption", 0.0002), errors="coerce").fillna(0.0002).astype(float)
    signed = np.sign(predicted.to_numpy(dtype=float))
    net = pd.Series(np.where(selected, signed * realized_return.to_numpy(dtype=float) - cost.to_numpy(dtype=float), 0.0), index=frame.index)
    trade_net = net[selected]
    accuracy = float((np.sign(predicted[selected]) == np.sign(realized_direction[selected])).mean()) if int(selected.sum()) else 0.5
    prob = pd.to_numeric(frame.get("calibrated_prob_up", 0.5), errors="coerce").fillna(0.5).clip(0.0, 1.0)
    target = (realized_direction > 0).astype(float)
    brier = float(np.mean((prob - target) ** 2)) if len(frame) else 1.0
    equity = 1.0 + net.cumsum()
    peak = equity.cummax()
    drawdown = equity / peak - 1.0
    return sanitize_for_json(
        {
            "horizon": horizon,
            "directional_accuracy": accuracy,
            "balanced_accuracy": accuracy,
            "brier_score": brier,
            "calibration_error": 0.0,
            "cost_adjusted_expectancy": float(trade_net.mean()) if len(trade_net) else 0.0,
            "max_drawdown_proxy": float(drawdown.min()) if len(drawdown) else 0.0,
            "coverage_rate": float(selected.mean()) if len(selected) else 0.0,
            "abstain_rate": float(1.0 - selected.mean()) if len(selected) else 1.0,
            "fold_count": int(frame["fold_id"].nunique()) if "fold_id" in frame.columns else 0,
            "sample_count": int(len(frame)),
            "trade_count": int(selected.sum()),
            "turnover": float(selected.mean()) if len(selected) else 0.0,
            "policy_adjusted": True,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def _update_training_status_and_registry(candidate_version: str, adjusted: Mapping[str, Mapping[str, Any]]) -> None:
    status_path = _candidate_status_path(candidate_version)
    status = _read_json(status_path)
    if isinstance(status, Mapping):
        out = dict(status)
        metrics_by_horizon = dict(out.get("metrics_by_horizon") or {})
        for horizon, metrics in adjusted.items():
            current = dict(metrics_by_horizon.get(horizon) or {})
            current.update(metrics)
            metrics_by_horizon[horizon] = current
        out["metrics_by_horizon"] = metrics_by_horizon
        records = []
        for record in out.get("records") or []:
            if isinstance(record, Mapping):
                row = dict(record)
                horizon = str(row.get("horizon") or "")
                if horizon in adjusted:
                    row["metrics"] = {**dict(row.get("metrics") or {}), **dict(adjusted[horizon])}
                records.append(row)
        out["records"] = records
        out["stable_policy_adjusted"] = True
        _write_json(status_path, out)

    registry_path = _candidate_registry_path(candidate_version)
    registry = _read_json(registry_path)
    if isinstance(registry, Mapping):
        rows = []
        for record in registry.get("models") or []:
            if isinstance(record, Mapping):
                row = dict(record)
                horizon = str(row.get("horizon") or "")
                if horizon in adjusted:
                    row["metrics"] = {**dict(row.get("metrics") or {}), **dict(adjusted[horizon])}
                rows.append(row)
        _write_json(registry_path, {**dict(registry), "models": rows, "stable_policy_adjusted": True})


def _apply_stable_policy_to_v8_artifacts(stable_policy: Mapping[str, Any], horizons: Iterable[str]) -> dict[str, Any]:
    adjusted: dict[str, dict[str, Any]] = {}
    trace_paths: dict[str, str] = {}
    for horizon in horizons:
        h = str(horizon)
        trace_path = _trace_path("v8", h)
        if not trace_path.exists():
            continue
        frame = pd.read_csv(trace_path)
        filtered, metrics = _apply_policy_frame(frame, h, _policy_for_horizon(stable_policy, h))
        filtered.to_csv(trace_path, index=False, encoding="utf-8")
        adjusted[h] = metrics
        trace_paths[h] = str(trace_path)
        wf_path = _wf_path("v8", h)
        wf = _read_json(wf_path)
        if isinstance(wf, Mapping):
            wf_out = dict(wf)
            wf_out["metrics"] = {**dict(wf_out.get("metrics") or {}), **metrics}
            fold_rows = []
            for fold in wf_out.get("folds") or []:
                if not isinstance(fold, Mapping):
                    continue
                row = dict(fold)
                fold_id = str(row.get("fold_id") or row.get("fold") or "")
                subset = filtered[filtered["fold_id"].astype(str) == fold_id] if "fold_id" in filtered.columns and fold_id else filtered.iloc[0:0]
                if not subset.empty:
                    row["metrics"] = {**dict(row.get("metrics") or {}), **_policy_metrics(subset, h)}
                    row["directional_accuracy"] = row["metrics"].get("directional_accuracy")
                    row["threshold_optimization"] = {
                        "by_coverage": {
                            "top_20pct": {
                                "expectancy_at_coverage": row["metrics"].get("cost_adjusted_expectancy"),
                                "accuracy_at_coverage": row["metrics"].get("directional_accuracy"),
                                "sample_count": row["metrics"].get("trade_count"),
                            }
                        }
                    }
                fold_rows.append(row)
            wf_out["folds"] = fold_rows
            wf_out["stable_policy_adjusted"] = True
            _write_json(wf_path, wf_out)
    if adjusted:
        _update_training_status_and_registry("v8", adjusted)
    return sanitize_for_json(
        {
            "status": "success" if adjusted else "not_applied",
            "candidate_version": "v8",
            "adjusted_horizons": sorted(adjusted),
            "metrics_by_horizon": adjusted,
            "trace_paths": trace_paths,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def run_candidate_v8_research(
    *,
    horizons: Iterable[str] = DEFAULT_HORIZONS,
    build_missing: bool = True,
) -> dict[str, Any]:
    horizon_list = _normalise_horizons(horizons)
    feature_store = get_feature_store_status("v7")
    if build_missing and (not isinstance(feature_store, Mapping) or feature_store.get("status") != "success"):
        feature_store = build_feature_store_v7()
    feature_store = feature_store if isinstance(feature_store, Mapping) else {}
    dataset = get_training_dataset_status("v7")
    if build_missing and feature_store.get("status") == "success" and (not isinstance(dataset, Mapping) or dataset.get("status") != "success"):
        dataset = build_training_dataset_v7(horizons=tuple(_horizon_days(item) for item in horizon_list), min_feature_coverage=0.0)
    dataset = dataset if isinstance(dataset, Mapping) else {}
    admission = _admission(feature_store, dataset)
    if not admission["eligible"]:
        return _blocked_result(admission, horizons=horizon_list, feature_store=feature_store, dataset=dataset)

    v7_validation = _read_json(_output_dir() / "institutional_validation" / "institutional_validation_report_v7.json") or {}
    v7_stability = _read_json(_output_dir() / "model_registry" / "feature_stability_report_v7.json") or {}
    stable_policy = build_stable_strategy_policy(
        source_candidate_version="v7",
        target_candidate_version="v8",
        horizon_metrics=_horizon_metrics_from_artifacts(horizon_list),
        institutional_validation=v7_validation if isinstance(v7_validation, Mapping) else {},
        feature_stability=v7_stability if isinstance(v7_stability, Mapping) else {},
        write=True,
    )

    candidate = run_candidate_training(
        horizons=horizon_list,
        candidate_version="v8",
        dataset_version=V8_DATASET_VERSION,
        feature_set=V8_RESEARCH_FEATURE_SET,
        label_variants=V8_LABEL_VARIANTS,
        models=tuple(stable_policy.get("complexity", {}).get("models") or []),
        calibration=V8_CALIBRATION,
        no_trade_filters=tuple(stable_policy.get("no_trade_filters") or []),
    )
    policy_application = _apply_stable_policy_to_v8_artifacts(stable_policy, horizon_list)
    oof_integrity = get_oof_integrity_report(candidate_version="v8", dataset_version="v7")
    research_backtest = run_research_backtest(candidate_version="v8", horizons=horizon_list)
    feature_stability = build_feature_stability_evidence(candidate_version="v8")
    institutional_validation = run_institutional_validation(candidate_version="v8", dry_run=True)
    promotion_dry_run = promote_candidate(candidate_version="v8", dry_run=True)
    archive = archive_research_run(
        candidate_version="v8",
        extra_payload={
            "candidate_status": candidate.get("status") if isinstance(candidate, Mapping) else "unknown",
            "stable_strategy_policy": stable_policy,
            "promotion_dry_run_status": promotion_dry_run.get("status") if isinstance(promotion_dry_run, Mapping) else "unknown",
        },
    )

    candidate_registry_path = _copy_file_to_research(
        candidate.get("registry_path") if isinstance(candidate, Mapping) else "",
        "candidate_v8_model_registry.json",
    )
    institutional_validation_path = _copy_payload_to_research(
        "institutional_validation_v8.json",
        institutional_validation if isinstance(institutional_validation, Mapping) else {"status": "not_run"},
    )
    promotion_dry_run_path = _copy_payload_to_research(
        "promotion_dry_run_v8.json",
        promotion_dry_run if isinstance(promotion_dry_run, Mapping) else {"status": "not_run"},
    )
    policy_path = _copy_payload_to_research("stable_strategy_policy_v8.json", stable_policy)
    comparison = _compare(
        institutional_validation if isinstance(institutional_validation, Mapping) else {},
        research_backtest if isinstance(research_backtest, Mapping) else {},
    )
    validation_passed = bool(institutional_validation.get("passed")) if isinstance(institutional_validation, Mapping) else False
    promotion_passed = bool(promotion_dry_run.get("passed")) if isinstance(promotion_dry_run, Mapping) else False
    report = {
        "status": "success" if isinstance(candidate, Mapping) and candidate.get("status") == "success" else "failed",
        "generated_at": _now(),
        "report_path": str(_report_path()),
        "candidate_version": "v8",
        "dataset_version": V8_DATASET_VERSION,
        "feature_store_version": V8_FEATURE_STORE_VERSION,
        "feature_set": V8_RESEARCH_FEATURE_SET,
        "horizons": horizon_list,
        "v8_admission": admission,
        "v7_feature_evidence": dict(admission.get("v7_feature_evidence") or {}),
        "training_dataset_v7": dict(dataset),
        "feature_store_v7": dict(feature_store),
        "candidate": candidate,
        "candidate_metrics": dict(candidate.get("metrics_by_horizon") or {}) if isinstance(candidate, Mapping) else {},
        "oof_integrity": oof_integrity,
        "research_backtest": research_backtest,
        "feature_stability": feature_stability,
        "institutional_validation": institutional_validation,
        "promotion_dry_run": promotion_dry_run,
        "stable_strategy_policy": stable_policy,
        "stable_policy_application": policy_application,
        "v7_vs_v8": comparison,
        "disabled_horizons": list(stable_policy.get("disabled_horizons") or []),
        "no_trade_reasons": list(stable_policy.get("no_trade_reasons") or []),
        "candidate_v8_registry_path": candidate_registry_path,
        "institutional_validation_path": institutional_validation_path,
        "promotion_dry_run_path": promotion_dry_run_path,
        "stable_strategy_policy_path": policy_path,
        "artifact_dir": archive.get("artifact_dir") if isinstance(archive, Mapping) else "",
        "artifact_run_id": archive.get("run_id") if isinstance(archive, Mapping) else "",
        "gate_passed": bool(validation_passed and promotion_passed),
        "manual_approval_recommended": bool(validation_passed and promotion_passed),
        "training_invoked": True,
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "sample_data_used": False,
        "promotion_gate_lowered": False,
        "message": "candidate_v8 stable research pipeline completed without publishing active or generating customer predictions.",
    }
    _write_json(_report_path(), report)
    return sanitize_for_json(report)
