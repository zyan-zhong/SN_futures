from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .candidate_v7_research_service import DEFAULT_HORIZONS, _horizon_days, _normalise_horizons
from .cpcv_validation_service import build_cpcv_report, build_cpcv_splits
from .feature_stability_evidence_service import build_feature_stability_evidence
from .institutional_validation_service import run_institutional_validation
from .model_promotion_service import promote_candidate
from .oof_integrity_service import get_oof_integrity_report
from .regime_balanced_dataset_service import build_training_dataset_v10
from .research_artifact_service import archive_research_run
from .research_backtest_service import run_research_backtest
from .training_dataset_service import get_training_dataset_status
from .walk_forward_training_service import run_candidate_training


V10_CANDIDATE_VERSION = "v10"
V10_FEATURE_STORE_VERSION = "v7"
V10_DATASET_VERSION = "v10"
V10_RESEARCH_FEATURE_SET = "regime_balanced_cpcv"
V10_LABEL_VARIANTS = (
    "direction_thresholded",
    "volatility_adjusted_direction",
    "triple_barrier_atr",
    "meta_label_tradeability",
)
V10_MODELS = (
    "sklearn_hist_gradient",
    "extra_trees",
    "random_forest",
)
V10_CALIBRATION = ("sigmoid",)
V10_NO_TRADE_FILTERS = (
    "low_confidence",
    "low_edge",
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
    "cpcv_path_guard",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _research_dir() -> Path:
    path = _output_dir() / "model_research" / "candidate_v10"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_path() -> Path:
    return _research_dir() / "candidate_v10_gated_research_report.json"


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


def _copy_payload_to_research(filename: str, payload: Mapping[str, Any]) -> str:
    path = _research_dir() / filename
    _write_json(path, payload)
    return str(path)


def _copy_file_to_research(source: str | None, filename: str) -> str:
    if not source:
        return ""
    src = Path(str(source))
    if not src.exists():
        return ""
    target = _research_dir() / filename
    target.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(src, target)
    except Exception:
        return ""
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


def _manifest_sample_or_mock(payload: Mapping[str, Any]) -> bool:
    return bool(payload.get("sample_data_used") or payload.get("mock_data_used") or payload.get("baseline_used"))


def _dataset_sample_count(dataset: Mapping[str, Any]) -> int:
    outputs = dataset.get("dataset_outputs")
    if isinstance(outputs, Mapping):
        counts = [
            int(_safe_float(payload.get("sample_count"), 0))
            for payload in outputs.values()
            if isinstance(payload, Mapping)
        ]
        if counts:
            return max(counts)
    horizon_counts = dataset.get("horizon_regime_counts")
    if isinstance(horizon_counts, Mapping):
        counts = [
            sum(int(_safe_float(value, 0)) for value in payload.values())
            for payload in horizon_counts.values()
            if isinstance(payload, Mapping)
        ]
        if counts:
            return max(counts)
    return int(_safe_float(dataset.get("sample_count"), 0))


def _admission(dataset: Mapping[str, Any]) -> dict[str, Any]:
    blocked: list[str] = []
    if not dataset or dataset.get("status") != "success":
        blocked.append("dataset_v10_not_ready")
    version = str(dataset.get("dataset_version") or dataset.get("version") or "").lower() if dataset else ""
    if dataset and version not in {"v10", "10"}:
        blocked.append("dataset_v10_not_ready")
    if dataset and not bool(dataset.get("leakage_check_pass")):
        blocked.append("leakage_check_failed")
    if dataset and not bool(dataset.get("no_lookahead_pass", True)):
        blocked.append("no_lookahead_failed")
    if dataset and bool(dataset.get("sample_data_used")):
        blocked.append("sample_data_used")
    if dataset and bool(dataset.get("mock_data_used")):
        blocked.append("mock_data_used")
    if dataset and bool(dataset.get("baseline_used")):
        blocked.append("baseline_used")

    regime_distribution = dataset.get("regime_distribution") if isinstance(dataset.get("regime_distribution"), Mapping) else {}
    horizon_regime_counts = dataset.get("horizon_regime_counts") if isinstance(dataset.get("horizon_regime_counts"), Mapping) else {}
    regime_sample_weights = dataset.get("regime_sample_weights") if isinstance(dataset.get("regime_sample_weights"), Mapping) else {}
    if not regime_distribution:
        blocked.append("regime_distribution_missing")
    if not horizon_regime_counts:
        blocked.append("horizon_regime_counts_missing")
    if not regime_sample_weights:
        blocked.append("regime_sample_weights_missing")

    sample_count = _dataset_sample_count(dataset)
    cpcv_splits = build_cpcv_splits(sample_count=sample_count, n_groups=6, test_group_count=2, purge=1, embargo=1) if sample_count > 0 else []
    if not cpcv_splits:
        blocked.append("cpcv_splitter_not_ready")

    return {
        "eligible": not blocked,
        "stage": "candidate_v10_admission",
        "candidate_version": V10_CANDIDATE_VERSION,
        "dataset_version": V10_DATASET_VERSION,
        "feature_store_version": V10_FEATURE_STORE_VERSION,
        "blocked_reasons": sorted(set(blocked)),
        "regime_distribution": dict(regime_distribution),
        "horizon_regime_counts": dict(horizon_regime_counts),
        "regime_sample_weights": dict(regime_sample_weights),
        "cpcv_split_count": len(cpcv_splits),
        "sample_count_for_cpcv": sample_count,
        "sample_data_used": bool(dataset.get("sample_data_used")) if dataset else False,
        "mock_data_used": bool(dataset.get("mock_data_used")) if dataset else False,
        "baseline_used": bool(dataset.get("baseline_used")) if dataset else False,
    }


def _blocked_result(admission: Mapping[str, Any], *, horizons: tuple[str, ...], dataset: Mapping[str, Any]) -> dict[str, Any]:
    report = {
        "status": "blocked",
        "generated_at": _now(),
        "report_path": str(_report_path()),
        "candidate_version": V10_CANDIDATE_VERSION,
        "dataset_version": V10_DATASET_VERSION,
        "feature_store_version": V10_FEATURE_STORE_VERSION,
        "feature_set": V10_RESEARCH_FEATURE_SET,
        "horizons": list(horizons),
        "v10_admission": dict(admission),
        "training_dataset_v10": dict(dataset),
        "blocking_reasons": list(admission.get("blocked_reasons") or ["admission_failed"]),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "sample_data_used": bool(dataset.get("sample_data_used")) if isinstance(dataset, Mapping) else False,
        "mock_data_used": bool(dataset.get("mock_data_used")) if isinstance(dataset, Mapping) else False,
        "promotion_gate_lowered": False,
        "manual_approval_recommended": False,
        "message": "candidate_v10 blocked before training; active remains unchanged and no customer prediction was generated.",
    }
    _write_json(_report_path(), report)
    return sanitize_for_json(report)


def _metric_summary(
    validation: Mapping[str, Any],
    backtest: Mapping[str, Any],
    cpcv: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    cpcv = cpcv if isinstance(cpcv, Mapping) else {}
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
    if not two_x_values:
        two_x_values = [_safe_float(_nested(validation, "cost_stress", "2x_cost", "expectancy"), 0.0)]
    if not three_x_values:
        three_x_values = [_safe_float(_nested(validation, "cost_stress", "3x_cost", "expectancy"), 0.0)]

    cpcv_pbo = _safe_float(_nested(cpcv, "pbo", "pbo"), np.nan)
    cpcv_reality = _safe_float(_nested(cpcv, "reality_check", "aggregate_p_value"), np.nan)
    return {
        "PBO": cpcv_pbo if np.isfinite(cpcv_pbo) else _safe_float(_nested(validation, "probability_of_backtest_overfitting", "pbo"), _safe_float(validation.get("pbo"), 0.0)),
        "DSR": _safe_float(_nested(validation, "deflated_sharpe_ratio", "deflated_sharpe_ratio"), _safe_float(validation.get("dsr"), 0.0)),
        "Reality Check p-value": cpcv_reality if np.isfinite(cpcv_reality) else _safe_float(_nested(validation, "reality_check", "p_value"), _safe_float(validation.get("reality_check_p_value"), 1.0)),
        "regime concentration": _safe_float(_nested(validation, "dominance_checks", "single_regime_contribution"), 1.0),
        "fold concentration": _safe_float(_nested(validation, "dominance_checks", "single_fold_contribution"), 1.0),
        "year concentration": _safe_float(_nested(validation, "dominance_checks", "single_year_contribution"), 1.0),
        "2x cost expectancy": sum(two_x_values) / max(len(two_x_values), 1),
        "3x cost expectancy": sum(three_x_values) / max(len(three_x_values), 1),
        "max_drawdown": max_drawdown,
        "turnover": turnover,
        "trade_count": trade_count,
    }


def _previous_v9_summary() -> dict[str, Any]:
    report = _read_json(_output_dir() / "model_research" / "candidate_v9" / "candidate_v9_gated_research_report.json")
    if isinstance(report, Mapping):
        comparison = report.get("v8_vs_v9")
        if isinstance(comparison, Mapping) and isinstance(comparison.get("v9"), Mapping):
            return dict(comparison["v9"])

    validation = _read_json(_output_dir() / "institutional_validation" / "institutional_validation_report_v9.json") or {}
    horizons: dict[str, Any] = {}
    for path in sorted((_output_dir() / "research_backtests" / "v9").glob("metrics_*.json")):
        h = path.stem.replace("metrics_", "")
        metrics = _read_json(path) or {}
        horizons[h] = {"metrics": metrics}
    return _metric_summary(validation if isinstance(validation, Mapping) else {}, {"horizons": horizons})


def _compare(v10_validation: Mapping[str, Any], v10_backtest: Mapping[str, Any], v10_cpcv: Mapping[str, Any]) -> dict[str, Any]:
    before = _previous_v9_summary()
    after = _metric_summary(v10_validation, v10_backtest, v10_cpcv)
    return {
        "v9": before,
        "v10": after,
        "improvement": {
            "PBO": _safe_float(before.get("PBO"), 0.0) - _safe_float(after.get("PBO"), 0.0),
            "DSR": _safe_float(after.get("DSR"), 0.0) - _safe_float(before.get("DSR"), 0.0),
            "Reality Check p-value": _safe_float(before.get("Reality Check p-value"), 1.0) - _safe_float(after.get("Reality Check p-value"), 1.0),
            "regime concentration": _safe_float(before.get("regime concentration"), 0.0) - _safe_float(after.get("regime concentration"), 0.0),
            "fold concentration": _safe_float(before.get("fold concentration"), 0.0) - _safe_float(after.get("fold concentration"), 0.0),
            "year concentration": _safe_float(before.get("year concentration"), 0.0) - _safe_float(after.get("year concentration"), 0.0),
            "max_drawdown_abs": abs(_safe_float(before.get("max_drawdown"), 0.0)) - abs(_safe_float(after.get("max_drawdown"), 0.0)),
            "turnover": _safe_float(before.get("turnover"), 0.0) - _safe_float(after.get("turnover"), 0.0),
            "trade_count": int(_safe_float(before.get("trade_count"), 0)) - int(_safe_float(after.get("trade_count"), 0)),
        },
    }


def _gate_checks(validation: Mapping[str, Any], cpcv: Mapping[str, Any], backtest: Mapping[str, Any] | None = None) -> dict[str, Any]:
    pbo = _safe_float(_nested(cpcv, "pbo", "pbo"), _safe_float(_nested(validation, "probability_of_backtest_overfitting", "pbo"), 1.0))
    reality_pass = bool(_nested(cpcv, "reality_check", "passed"))
    if not reality_pass:
        reality_pass = bool(_nested(validation, "reality_check", "passed"))
    has_regime = _nested(validation, "dominance_checks", "single_regime_contribution") is not None
    has_fold = _nested(validation, "dominance_checks", "single_fold_contribution") is not None
    has_year = _nested(validation, "dominance_checks", "single_year_contribution") is not None
    regime_concentration = _safe_float(_nested(validation, "dominance_checks", "single_regime_contribution"), 1.0)
    fold_concentration = _safe_float(_nested(validation, "dominance_checks", "single_fold_contribution"), 1.0)
    year_concentration = _safe_float(_nested(validation, "dominance_checks", "single_year_contribution"), 1.0)
    two_x = _safe_float(_nested(validation, "cost_stress", "2x_cost", "expectancy"), 0.0)
    three_x = _safe_float(_nested(validation, "cost_stress", "3x_cost", "expectancy"), 0.0)
    research_summary = _metric_summary(validation, backtest or {}, cpcv)
    return {
        "pbo": pbo,
        "pbo_lt_0_2": bool(pbo < 0.2),
        "reality_check_pass": bool(reality_pass),
        "regime_concentration": regime_concentration,
        "regime_concentration_evidence_available": bool(has_regime),
        "regime_concentration_pass": bool(has_regime and regime_concentration <= 0.5),
        "fold_concentration": fold_concentration,
        "fold_concentration_evidence_available": bool(has_fold),
        "fold_concentration_pass": bool(has_fold and fold_concentration <= 0.5),
        "year_concentration": year_concentration,
        "year_concentration_evidence_available": bool(has_year),
        "year_concentration_pass": bool(has_year and year_concentration <= 0.5),
        "two_x_cost_expectancy": two_x,
        "three_x_cost_expectancy": three_x,
        "research_two_x_cost_expectancy": research_summary.get("2x cost expectancy"),
        "research_three_x_cost_expectancy": research_summary.get("3x cost expectancy"),
        "cost_pressure_positive": bool(two_x >= 0.0 and three_x >= 0.0),
    }


def run_candidate_v10_research(
    *,
    horizons: Iterable[str] = DEFAULT_HORIZONS,
    build_missing: bool = True,
) -> dict[str, Any]:
    horizon_list = _normalise_horizons(horizons)
    dataset = get_training_dataset_status("v10")
    if build_missing and (not isinstance(dataset, Mapping) or dataset.get("status") != "success"):
        dataset = build_training_dataset_v10(horizons=tuple(_horizon_days(item) for item in horizon_list), min_feature_coverage=0.0)
    dataset = dataset if isinstance(dataset, Mapping) else {}
    admission = _admission(dataset)
    if not admission["eligible"]:
        return _blocked_result(admission, horizons=horizon_list, dataset=dataset)

    candidate = run_candidate_training(
        horizons=horizon_list,
        candidate_version=V10_CANDIDATE_VERSION,
        dataset_version=V10_DATASET_VERSION,
        feature_set=V10_RESEARCH_FEATURE_SET,
        label_variants=V10_LABEL_VARIANTS,
        models=V10_MODELS,
        calibration=V10_CALIBRATION,
        no_trade_filters=V10_NO_TRADE_FILTERS,
    )
    oof_integrity = get_oof_integrity_report(candidate_version=V10_CANDIDATE_VERSION, dataset_version=V10_DATASET_VERSION)
    cpcv_validation = build_cpcv_report(candidate_version=V10_CANDIDATE_VERSION)
    research_backtest = run_research_backtest(candidate_version=V10_CANDIDATE_VERSION, horizons=horizon_list)
    feature_stability = build_feature_stability_evidence(candidate_version=V10_CANDIDATE_VERSION)
    institutional_validation = run_institutional_validation(candidate_version=V10_CANDIDATE_VERSION, dry_run=True)
    promotion_dry_run = promote_candidate(candidate_version=V10_CANDIDATE_VERSION, dry_run=True)
    archive = archive_research_run(
        candidate_version=V10_CANDIDATE_VERSION,
        extra_payload={
            "candidate_status": candidate.get("status") if isinstance(candidate, Mapping) else "unknown",
            "cpcv_status": cpcv_validation.get("status") if isinstance(cpcv_validation, Mapping) else "unknown",
            "promotion_dry_run_status": promotion_dry_run.get("status") if isinstance(promotion_dry_run, Mapping) else "unknown",
        },
    )
    candidate_registry_path = _copy_file_to_research(
        candidate.get("registry_path") if isinstance(candidate, Mapping) else "",
        "candidate_v10_model_registry.json",
    )
    institutional_validation_path = _copy_payload_to_research(
        "institutional_validation_v10.json",
        institutional_validation if isinstance(institutional_validation, Mapping) else {"status": "not_run"},
    )
    promotion_dry_run_path = _copy_payload_to_research(
        "promotion_dry_run_v10.json",
        promotion_dry_run if isinstance(promotion_dry_run, Mapping) else {"status": "not_run"},
    )
    cpcv_validation_path = _copy_payload_to_research(
        "cpcv_validation_v10.json",
        cpcv_validation if isinstance(cpcv_validation, Mapping) else {"status": "not_run"},
    )
    comparison = _compare(
        institutional_validation if isinstance(institutional_validation, Mapping) else {},
        research_backtest if isinstance(research_backtest, Mapping) else {},
        cpcv_validation if isinstance(cpcv_validation, Mapping) else {},
    )
    gate_checks = _gate_checks(
        institutional_validation if isinstance(institutional_validation, Mapping) else {},
        cpcv_validation if isinstance(cpcv_validation, Mapping) else {},
        research_backtest if isinstance(research_backtest, Mapping) else {},
    )
    validation_passed = bool(institutional_validation.get("passed")) if isinstance(institutional_validation, Mapping) else False
    promotion_passed = bool(promotion_dry_run.get("passed")) if isinstance(promotion_dry_run, Mapping) else False
    cpcv_passed = bool(gate_checks["pbo_lt_0_2"] and gate_checks["reality_check_pass"])
    concentration_passed = bool(
        gate_checks["regime_concentration_pass"]
        and gate_checks["fold_concentration_pass"]
        and gate_checks["year_concentration_pass"]
    )
    report = {
        "status": "success" if isinstance(candidate, Mapping) and candidate.get("status") == "success" else "failed",
        "generated_at": _now(),
        "report_path": str(_report_path()),
        "candidate_version": V10_CANDIDATE_VERSION,
        "base_candidate": "v9",
        "dataset_version": V10_DATASET_VERSION,
        "feature_store_version": V10_FEATURE_STORE_VERSION,
        "feature_set": V10_RESEARCH_FEATURE_SET,
        "horizons": list(horizon_list),
        "v10_admission": admission,
        "training_dataset_v10": dict(dataset),
        "candidate": candidate,
        "candidate_metrics": dict(candidate.get("metrics_by_horizon") or {}) if isinstance(candidate, Mapping) else {},
        "oof_integrity": oof_integrity,
        "cpcv_validation": cpcv_validation,
        "research_backtest": research_backtest,
        "feature_stability": feature_stability,
        "institutional_validation": institutional_validation,
        "promotion_dry_run": promotion_dry_run,
        "v10_gate_checks": gate_checks,
        "v10_vs_v9": comparison,
        "candidate_v10_registry_path": candidate_registry_path,
        "institutional_validation_path": institutional_validation_path,
        "promotion_dry_run_path": promotion_dry_run_path,
        "cpcv_validation_path": cpcv_validation_path,
        "artifact_dir": archive.get("artifact_dir") if isinstance(archive, Mapping) else "",
        "artifact_run_id": archive.get("run_id") if isinstance(archive, Mapping) else "",
        "gate_passed": bool(validation_passed and promotion_passed and cpcv_passed and concentration_passed and gate_checks["cost_pressure_positive"]),
        "manual_approval_recommended": bool(validation_passed and promotion_passed and cpcv_passed and concentration_passed and gate_checks["cost_pressure_positive"]),
        "training_invoked": True,
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "sample_data_used": False,
        "mock_data_used": False,
        "promotion_gate_lowered": False,
        "message": "candidate_v10 regime-balanced CPCV research pipeline completed without publishing active or generating customer predictions.",
    }
    _write_json(_report_path(), report)
    return sanitize_for_json(report)
