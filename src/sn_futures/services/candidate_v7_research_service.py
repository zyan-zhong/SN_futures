from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .feature_stability_evidence_service import build_feature_stability_evidence
from .feature_store_service import get_feature_store_status
from .feature_store_v7_service import V7_FEATURE_SET, build_feature_store_v7, build_training_dataset_v7
from .institutional_validation_service import run_institutional_validation
from .model_promotion_service import promote_candidate
from .model_stability_optimizer import optimize_stability_objective
from .oof_integrity_service import get_oof_integrity_report
from .research_artifact_service import archive_research_run
from .research_backtest_service import run_research_backtest
from .training_dataset_service import get_training_dataset_status
from .walk_forward_training_service import run_candidate_training


DEFAULT_HORIZONS = ("1d", "3d", "5d", "10d", "20d")
V7_FEATURE_STORE_VERSION = "v7"
V7_DATASET_VERSION = "v7"
V7_RESEARCH_FEATURE_SET = "tushare_cost_positioning_enhanced"
V7_LABEL_VARIANTS = (
    "direction_thresholded",
    "volatility_adjusted_direction",
    "triple_barrier_atr",
    "meta_label_tradeability",
)
V7_MODELS = (
    "hist_gradient_boosting",
    "extra_trees",
    "random_forest",
    "compact_lightgbm_if_available",
    "huber_return",
    "elasticnet_return",
)
V7_CALIBRATION = ("sigmoid", "isotonic")
V7_NO_TRADE_FILTERS = (
    "low_confidence",
    "low_edge",
    "high_volatility",
    "high_cost_pressure",
    "stale_data",
    "low_liquidity",
    "sparse_holding_missing",
    "roll_period",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _research_dir() -> Path:
    path = _output_dir() / "model_research" / "candidate_v7"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_path() -> Path:
    return _research_dir() / "candidate_v7_gated_research_report.json"


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


def _horizon_days(horizon: str) -> int:
    try:
        return max(1, int(str(horizon).lower().replace("d", "")))
    except Exception:
        return 1


def _normalise_horizons(horizons: Iterable[str]) -> tuple[str, ...]:
    values = tuple(str(item) for item in horizons)
    return values or DEFAULT_HORIZONS


def _manifest_sample_or_mock(payload: Mapping[str, Any]) -> bool:
    return bool(payload.get("sample_data_used") or payload.get("mock_data_used") or payload.get("baseline_used"))


def _v7_feature_evidence(feature_store: Mapping[str, Any], dataset: Mapping[str, Any]) -> dict[str, Any]:
    cost = [str(item) for item in feature_store.get("cost_features") or dataset.get("cost_features") or []]
    positioning = [str(item) for item in feature_store.get("positioning_features") or dataset.get("positioning_features") or []]
    sparse = [str(item) for item in feature_store.get("sparse_features") or dataset.get("sparse_features") or []]
    return {
        "cost_features": cost,
        "positioning_features": positioning,
        "sparse_features": sparse,
        "usable_cost_features": sorted(set(cost).intersection(set(dataset.get("feature_cols") or feature_store.get("usable_fields") or []))),
        "usable_positioning_features": sorted(set(positioning).intersection(set(dataset.get("feature_cols") or feature_store.get("usable_fields") or []))),
        "sparse_feature_policy": feature_store.get("sparse_feature_policy") or dataset.get("sparse_feature_policy") or {},
    }


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
        "stage": "candidate_v7_admission",
        "candidate_version": "v7",
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
        "candidate_version": "v7",
        "dataset_version": V7_DATASET_VERSION,
        "feature_store_version": V7_FEATURE_STORE_VERSION,
        "feature_set": V7_RESEARCH_FEATURE_SET,
        "horizons": horizons,
        "v7_admission": dict(admission),
        "v7_feature_evidence": dict(admission.get("v7_feature_evidence") or {}),
        "feature_store_v7": dict(feature_store),
        "training_dataset_v7": dict(dataset),
        "blocked_reasons": list(admission.get("blocked_reasons") or []),
        "blocking_reasons": list(admission.get("blocked_reasons") or []),
        "candidate": {"status": "not_run"},
        "research_backtest": {"status": "not_run"},
        "institutional_validation": {"status": "not_run"},
        "promotion_dry_run": {"status": "not_run"},
        "stability_objective": {"status": "not_run"},
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


def _previous_v6_comparison(v7_validation: Mapping[str, Any], v7_backtest: Mapping[str, Any]) -> dict[str, Any]:
    v6_validation = _read_json(_output_dir() / "institutional_validation" / "institutional_validation_report_v6.json") or {}
    v6_backtest = _read_json(_output_dir() / "research_backtests" / "v6" / "metrics_1d.json") or {}
    v7_horizons = v7_backtest.get("horizons") if isinstance(v7_backtest.get("horizons"), Mapping) else {}
    first_v7 = next(iter(v7_horizons.values()), {}) if v7_horizons else {}
    first_v7_metrics = first_v7.get("metrics") if isinstance(first_v7, Mapping) and isinstance(first_v7.get("metrics"), Mapping) else {}
    return {
        "v6": {
            "PBO": _nested_float(v6_validation, ("probability_of_backtest_overfitting", "pbo")),
            "DSR": _nested_float(v6_validation, ("deflated_sharpe_ratio", "deflated_sharpe_ratio")),
            "Reality Check p-value": _nested_float(v6_validation, ("reality_check", "p_value"), 1.0),
            "2x cost expectancy": _nested_float(v6_backtest, ("cost_stress", "2x_cost", "expectancy")),
            "3x cost expectancy": _nested_float(v6_backtest, ("cost_stress", "3x_cost", "expectancy")),
        },
        "v7": {
            "PBO": _nested_float(v7_validation, ("probability_of_backtest_overfitting", "pbo")),
            "DSR": _nested_float(v7_validation, ("deflated_sharpe_ratio", "deflated_sharpe_ratio")),
            "Reality Check p-value": _nested_float(v7_validation, ("reality_check", "p_value"), 1.0),
            "2x cost expectancy": _nested_float(first_v7_metrics, ("cost_stress", "2x_cost", "expectancy")),
            "3x cost expectancy": _nested_float(first_v7_metrics, ("cost_stress", "3x_cost", "expectancy")),
        },
    }


def _nested_float(payload: Mapping[str, Any], keys: tuple[str, ...], default: float = 0.0) -> float:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return default
        current = current.get(key)
    try:
        return float(current)
    except (TypeError, ValueError):
        return default


def run_candidate_v7_research(
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

    candidate = run_candidate_training(
        horizons=horizon_list,
        candidate_version="v7",
        dataset_version=V7_DATASET_VERSION,
        feature_set=V7_RESEARCH_FEATURE_SET,
        label_variants=V7_LABEL_VARIANTS,
        models=V7_MODELS,
        calibration=V7_CALIBRATION,
        no_trade_filters=V7_NO_TRADE_FILTERS,
    )
    oof_integrity = get_oof_integrity_report(candidate_version="v7", dataset_version="v7")
    research_backtest = run_research_backtest(candidate_version="v7", horizons=horizon_list)
    feature_stability = build_feature_stability_evidence(candidate_version="v7")
    institutional_validation = run_institutional_validation(candidate_version="v7", dry_run=True)
    stability_objective = optimize_stability_objective(
        candidate_version="v7",
        institutional_validation=institutional_validation if isinstance(institutional_validation, Mapping) else {},
        research_backtest=research_backtest if isinstance(research_backtest, Mapping) else {},
        feature_stability=feature_stability if isinstance(feature_stability, Mapping) else {},
    )
    promotion_dry_run = promote_candidate(candidate_version="v7", dry_run=True)
    archive = archive_research_run(
        candidate_version="v7",
        extra_payload={
            "candidate_status": candidate.get("status") if isinstance(candidate, Mapping) else "unknown",
            "stability_objective": stability_objective,
            "promotion_dry_run_status": promotion_dry_run.get("status") if isinstance(promotion_dry_run, Mapping) else "unknown",
        },
    )

    candidate_registry_path = _copy_file_to_research(
        candidate.get("registry_path") if isinstance(candidate, Mapping) else "",
        "candidate_v7_model_registry.json",
    )
    institutional_validation_path = _copy_payload_to_research(
        "institutional_validation_v7.json",
        institutional_validation if isinstance(institutional_validation, Mapping) else {"status": "not_run"},
    )
    promotion_dry_run_path = _copy_payload_to_research(
        "promotion_dry_run_v7.json",
        promotion_dry_run if isinstance(promotion_dry_run, Mapping) else {"status": "not_run"},
    )
    stability_objective_path = _copy_payload_to_research("stability_objective_v7.json", stability_objective)
    comparison = _previous_v6_comparison(
        institutional_validation if isinstance(institutional_validation, Mapping) else {},
        research_backtest if isinstance(research_backtest, Mapping) else {},
    )
    validation_passed = bool(institutional_validation.get("passed")) if isinstance(institutional_validation, Mapping) else False
    promotion_passed = bool(promotion_dry_run.get("passed")) if isinstance(promotion_dry_run, Mapping) else False
    report = {
        "status": "success" if isinstance(candidate, Mapping) and candidate.get("status") == "success" else "failed",
        "generated_at": _now(),
        "report_path": str(_report_path()),
        "candidate_version": "v7",
        "dataset_version": V7_DATASET_VERSION,
        "feature_store_version": V7_FEATURE_STORE_VERSION,
        "feature_set": V7_RESEARCH_FEATURE_SET,
        "horizons": horizon_list,
        "v7_admission": admission,
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
        "stability_objective": stability_objective,
        "v6_vs_v7": comparison,
        "candidate_v7_registry_path": candidate_registry_path,
        "institutional_validation_path": institutional_validation_path,
        "promotion_dry_run_path": promotion_dry_run_path,
        "stability_objective_path": stability_objective_path,
        "artifact_dir": archive.get("artifact_dir") if isinstance(archive, Mapping) else "",
        "artifact_run_id": archive.get("run_id") if isinstance(archive, Mapping) else "",
        "gate_passed": bool(validation_passed and promotion_passed),
        "manual_approval_recommended": bool(validation_passed and promotion_passed and stability_objective.get("promotion_recommended")),
        "training_invoked": True,
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "sample_data_used": False,
        "promotion_gate_lowered": False,
        "message": "candidate_v7 research pipeline completed without publishing active or generating customer predictions.",
    }
    _write_json(_report_path(), report)
    return sanitize_for_json(report)
