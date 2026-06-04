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
from .candidate_v8_diagnostics_service import build_candidate_v8_validation_diagnostics
from .feature_stability_evidence_service import build_feature_stability_evidence
from .feature_store_service import get_feature_store_status
from .feature_store_v7_service import build_feature_store_v7, build_training_dataset_v7
from .institutional_validation_service import run_institutional_validation
from .model_promotion_service import promote_candidate
from .oof_integrity_service import get_oof_integrity_report
from .regime_neutral_strategy_service import (
    build_regime_neutral_strategy_policy,
    horizon_to_regime,
    select_regime_neutral_trades,
)
from .research_artifact_service import archive_research_run
from .research_backtest_service import run_research_backtest
from .training_dataset_service import get_training_dataset_status
from .walk_forward_training_service import run_candidate_training


V9_CANDIDATE_VERSION = "v9"
V9_FEATURE_STORE_VERSION = "v7"
V9_DATASET_VERSION = "v7"
V9_RESEARCH_FEATURE_SET = "tushare_cost_positioning_regime_neutral"
V9_LABEL_VARIANTS = (
    "direction_thresholded",
    "volatility_adjusted_direction",
    "triple_barrier_atr",
    "meta_label_tradeability",
)
V9_CALIBRATION = ("sigmoid",)
V9_NO_TRADE_FILTERS = (
    "low_confidence",
    "low_edge",
    "high_volatility",
    "high_cost_pressure",
    "stale_data",
    "low_liquidity",
    "sparse_holding_missing",
    "roll_period",
    "drawdown_guard",
    "regime_guard",
    "regime_trade_quota",
    "fold_trade_quota",
    "year_trade_quota",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _research_dir() -> Path:
    path = _output_dir() / "model_research" / "candidate_v9"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_path() -> Path:
    return _research_dir() / "candidate_v9_gated_research_report.json"


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
        "stage": "candidate_v9_admission",
        "candidate_version": "v9",
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
        "candidate_version": "v9",
        "dataset_version": V9_DATASET_VERSION,
        "feature_store_version": V9_FEATURE_STORE_VERSION,
        "feature_set": V9_RESEARCH_FEATURE_SET,
        "horizons": horizons,
        "v9_admission": dict(admission),
        "v7_feature_evidence": dict(admission.get("v7_feature_evidence") or {}),
        "feature_store_v7": dict(feature_store),
        "training_dataset_v7": dict(dataset),
        "blocked_reasons": list(admission.get("blocked_reasons") or []),
        "candidate": {"status": "not_run"},
        "research_backtest": {"status": "not_run"},
        "institutional_validation": {"status": "not_run"},
        "promotion_dry_run": {"status": "not_run"},
        "regime_neutral_policy": {"status": "not_run"},
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
    if str(source or "").strip() and src.exists() and src.is_file():
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, target)
    else:
        _write_json(target, {"status": "missing_source", "source": str(source or "")})
    return str(target)


def _trace_path(candidate_version: str, horizon: str) -> Path:
    return _output_dir() / "walk_forward" / str(candidate_version) / f"oof_trace_{horizon}.csv"


def _wf_path(candidate_version: str, horizon: str) -> Path:
    return _output_dir() / "walk_forward" / str(candidate_version) / f"wf_{horizon}.json"


def _candidate_status_path(candidate_version: str) -> Path:
    return _output_dir() / "model_registry" / f"candidate_{candidate_version}_training_status.json"


def _candidate_registry_path(candidate_version: str) -> Path:
    return _output_dir() / "model_registry" / f"candidate_{candidate_version}_model_registry.json"


def _policy_metrics(frame: pd.DataFrame, horizon: str) -> dict[str, Any]:
    selected = frame.get("regime_neutral_selected")
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
            "regime_neutral_policy_adjusted": True,
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
        out["regime_neutral_policy_adjusted"] = True
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
        _write_json(registry_path, {**dict(registry), "models": rows, "regime_neutral_policy_adjusted": True})


def _apply_regime_neutral_policy_to_v9_artifacts(policy: Mapping[str, Any], horizons: Iterable[str]) -> dict[str, Any]:
    frames: list[pd.DataFrame] = []
    for horizon in horizons:
        h = str(horizon)
        path = _trace_path("v9", h)
        if not path.exists():
            continue
        frame = pd.read_csv(path)
        if frame.empty:
            continue
        frame["__horizon"] = h
        frame["__row_order"] = np.arange(len(frame))
        if "regime_label" not in frame.columns:
            frame["regime_label"] = horizon_to_regime(h)
        frames.append(frame)
    if not frames:
        return {
            "status": "not_applied",
            "candidate_version": "v9",
            "adjusted_horizons": [],
            "metrics_by_horizon": {},
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    combined = pd.concat(frames, ignore_index=True)
    selected = select_regime_neutral_trades(combined, policy)
    combined["regime_neutral_selected"] = selected.astype(bool)
    combined["regime_neutral_reason"] = np.where(combined["regime_neutral_selected"], "selected", "quota_or_threshold_no_trade")
    combined.loc[~combined["regime_neutral_selected"], "predicted_direction"] = 0
    combined.loc[~combined["regime_neutral_selected"], "trade_edge"] = 0.0
    if "expected_return" in combined.columns:
        combined.loc[~combined["regime_neutral_selected"], "expected_return"] = 0.0
    combined["selected_signal"] = np.where(combined["regime_neutral_selected"], "regime_neutral_selected", "regime_neutral_no_trade")
    combined["no_trade_reason"] = np.where(combined["regime_neutral_selected"], "", "regime_neutral_quota_or_threshold")

    adjusted: dict[str, dict[str, Any]] = {}
    trace_paths: dict[str, str] = {}
    for horizon in horizons:
        h = str(horizon)
        subset = combined[combined["__horizon"].astype(str) == h].sort_values("__row_order").drop(columns=["__horizon", "__row_order"], errors="ignore")
        if subset.empty:
            continue
        trace_path = _trace_path("v9", h)
        subset.to_csv(trace_path, index=False, encoding="utf-8")
        metrics = _policy_metrics(subset, h)
        adjusted[h] = metrics
        trace_paths[h] = str(trace_path)
        wf_path = _wf_path("v9", h)
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
                fold_subset = subset[subset["fold_id"].astype(str) == fold_id] if "fold_id" in subset.columns and fold_id else subset.iloc[0:0]
                if not fold_subset.empty:
                    fold_metrics = _policy_metrics(fold_subset, h)
                    row["metrics"] = {**dict(row.get("metrics") or {}), **fold_metrics}
                    row["directional_accuracy"] = fold_metrics.get("directional_accuracy")
                    row["threshold_optimization"] = {
                        "by_coverage": {
                            "top_20pct": {
                                "expectancy_at_coverage": fold_metrics.get("cost_adjusted_expectancy"),
                                "accuracy_at_coverage": fold_metrics.get("directional_accuracy"),
                                "sample_count": fold_metrics.get("trade_count"),
                            }
                        }
                    }
                fold_rows.append(row)
            wf_out["folds"] = fold_rows
            wf_out["regime_neutral_policy_adjusted"] = True
            _write_json(wf_path, wf_out)
    if adjusted:
        _update_training_status_and_registry("v9", adjusted)
    return sanitize_for_json(
        {
            "status": "success",
            "candidate_version": "v9",
            "adjusted_horizons": sorted(adjusted),
            "metrics_by_horizon": adjusted,
            "trace_paths": trace_paths,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


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
        "regime concentration": _safe_float(_nested(validation, "dominance_checks", "single_regime_contribution"), 0.0),
        "fold concentration": _safe_float(_nested(validation, "dominance_checks", "single_fold_contribution"), 0.0),
        "2x cost expectancy": sum(two_x_values) / max(len(two_x_values), 1),
        "3x cost expectancy": sum(three_x_values) / max(len(three_x_values), 1),
        "max_drawdown": max_drawdown,
        "turnover": turnover,
        "trade_count": trade_count,
    }


def _previous_v8_summary() -> dict[str, Any]:
    validation = _read_json(_output_dir() / "institutional_validation" / "institutional_validation_report_v8.json") or {}
    horizons: dict[str, Any] = {}
    for path in sorted((_output_dir() / "research_backtests" / "v8").glob("metrics_*.json")):
        h = path.stem.replace("metrics_", "")
        metrics = _read_json(path) or {}
        horizons[h] = {"metrics": metrics}
    return _metric_summary(validation if isinstance(validation, Mapping) else {}, {"horizons": horizons})


def _compare(v9_validation: Mapping[str, Any], v9_backtest: Mapping[str, Any]) -> dict[str, Any]:
    before = _previous_v8_summary()
    after = _metric_summary(v9_validation, v9_backtest)
    return {
        "v8": before,
        "v9": after,
        "improvement": {
            "PBO": before.get("PBO", 0.0) - after.get("PBO", 0.0),
            "DSR": after.get("DSR", 0.0) - before.get("DSR", 0.0),
            "Reality Check p-value": before.get("Reality Check p-value", 1.0) - after.get("Reality Check p-value", 1.0),
            "regime concentration": before.get("regime concentration", 0.0) - after.get("regime concentration", 0.0),
            "fold concentration": before.get("fold concentration", 0.0) - after.get("fold concentration", 0.0),
            "max_drawdown_abs": abs(_safe_float(before.get("max_drawdown"), 0.0)) - abs(_safe_float(after.get("max_drawdown"), 0.0)),
            "turnover": before.get("turnover", 0.0) - after.get("turnover", 0.0),
            "trade_count": before.get("trade_count", 0) - after.get("trade_count", 0),
        },
    }


def _load_v8_context() -> tuple[dict[str, Any], dict[str, Any]]:
    diagnostics = _read_json(_output_dir() / "model_research" / "candidate_v8" / "candidate_v8_validation_diagnostics.json")
    if not isinstance(diagnostics, Mapping):
        diagnostics = build_candidate_v8_validation_diagnostics()
    report = _read_json(_output_dir() / "model_research" / "candidate_v8" / "candidate_v8_gated_research_report.json")
    return (diagnostics if isinstance(diagnostics, dict) else {}, report if isinstance(report, dict) else {})


def run_candidate_v9_research(
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

    v8_diagnostics, v8_report = _load_v8_context()
    regime_policy = build_regime_neutral_strategy_policy(
        v8_diagnostics=v8_diagnostics,
        v8_report=v8_report,
        target_candidate_version="v9",
        write=True,
    )
    candidate = run_candidate_training(
        horizons=horizon_list,
        candidate_version="v9",
        dataset_version=V9_DATASET_VERSION,
        feature_set=V9_RESEARCH_FEATURE_SET,
        label_variants=V9_LABEL_VARIANTS,
        models=tuple(regime_policy.get("complexity", {}).get("models") or []),
        calibration=V9_CALIBRATION,
        no_trade_filters=V9_NO_TRADE_FILTERS,
    )
    policy_application = _apply_regime_neutral_policy_to_v9_artifacts(regime_policy, horizon_list)
    oof_integrity = get_oof_integrity_report(candidate_version="v9", dataset_version="v7")
    research_backtest = run_research_backtest(candidate_version="v9", horizons=horizon_list)
    feature_stability = build_feature_stability_evidence(candidate_version="v9")
    institutional_validation = run_institutional_validation(candidate_version="v9", dry_run=True)
    promotion_dry_run = promote_candidate(candidate_version="v9", dry_run=True)
    archive = archive_research_run(
        candidate_version="v9",
        extra_payload={
            "candidate_status": candidate.get("status") if isinstance(candidate, Mapping) else "unknown",
            "regime_neutral_policy": regime_policy,
            "promotion_dry_run_status": promotion_dry_run.get("status") if isinstance(promotion_dry_run, Mapping) else "unknown",
        },
    )
    candidate_registry_path = _copy_file_to_research(
        candidate.get("registry_path") if isinstance(candidate, Mapping) else "",
        "candidate_v9_model_registry.json",
    )
    institutional_validation_path = _copy_payload_to_research(
        "institutional_validation_v9.json",
        institutional_validation if isinstance(institutional_validation, Mapping) else {"status": "not_run"},
    )
    promotion_dry_run_path = _copy_payload_to_research(
        "promotion_dry_run_v9.json",
        promotion_dry_run if isinstance(promotion_dry_run, Mapping) else {"status": "not_run"},
    )
    policy_path = _copy_payload_to_research("regime_neutral_strategy_policy_v9.json", regime_policy)
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
        "candidate_version": "v9",
        "base_candidate": "v8",
        "dataset_version": V9_DATASET_VERSION,
        "feature_store_version": V9_FEATURE_STORE_VERSION,
        "feature_set": V9_RESEARCH_FEATURE_SET,
        "horizons": horizon_list,
        "v9_admission": admission,
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
        "regime_neutral_policy": regime_policy,
        "regime_neutral_policy_application": policy_application,
        "v8_vs_v9": comparison,
        "candidate_v9_registry_path": candidate_registry_path,
        "institutional_validation_path": institutional_validation_path,
        "promotion_dry_run_path": promotion_dry_run_path,
        "regime_neutral_policy_path": policy_path,
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
        "message": "candidate_v9 regime-neutral research pipeline completed without publishing active or generating customer predictions.",
    }
    _write_json(_report_path(), report)
    return sanitize_for_json(report)
