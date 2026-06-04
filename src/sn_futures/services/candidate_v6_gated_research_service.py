from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .cross_market_feature_join_service import CROSS_MARKET_VALUE_FIELDS
from .feature_store_service import EVENT_FACTOR_INPUT_FIELDS
from .feature_stability_evidence_service import get_feature_stability_evidence
from .institutional_validation_service import run_institutional_validation
from .model_promotion_service import promote_candidate
from .oof_integrity_service import get_oof_integrity_report
from .research_backtest_service import run_research_backtest
from .research_artifact_service import archive_research_run
from .training_dataset_service import build_training_dataset
from .walk_forward_training_service import run_candidate_training


DEFAULT_HORIZONS = ("1d", "3d", "5d", "10d", "20d")
V6_FEATURE_STORE_VERSION = "v6"
V6_DATASET_VERSION = "v6"
V6_FEATURE_SET = "institutional_tushare_enhanced"
V6_LABEL_VARIANTS = ("direction_thresholded", "volatility_adjusted_direction", "triple_barrier_atr")
V6_MODELS = ("hist_gradient_boosting", "extra_trees", "random_forest", "lightgbm_if_available", "huber_return", "elasticnet_return")
V6_CALIBRATION = ("sigmoid", "isotonic")
V6_NO_TRADE_FILTERS = (
    "low_confidence",
    "low_edge",
    "high_volatility",
    "stale_data",
    "event_shock",
    "roll_period",
    "high_turnover",
    "low_liquidity",
)

FACTOR_GROUP_FIELDS = {
    "raw_market": {
        "open_interest",
        "settlement",
    },
    "cross_market": set(str(item) for item in CROSS_MARKET_VALUE_FIELDS),
    "event": set(str(item) for item in EVENT_FACTOR_INPUT_FIELDS),
    "basis": {
        "spot_price",
        "spot_premium",
        "spot_futures_basis",
        "basis_zscore_60",
        "basis_mom_5",
        "basis_mom_20",
        "lme_shfe_spread",
    },
    "inventory": {
        "warehouse_receipt",
        "warehouse_receipt_delta_1w",
        "shfe_inventory",
        "shfe_inventory_delta_1w",
        "shfe_inventory_delta_4w",
        "shfe_warehouse_receipt",
        "lme_inventory",
        "lme_inventory_delta_1w",
    },
    "term_structure": {
        "near_contract_close",
        "far_contract_close",
        "near_far_spread",
        "term_structure_slope",
        "roll_yield_proxy",
        "near_open_interest",
        "far_open_interest",
        "open_interest_roll_ratio",
        "main_contract_switch_flag",
    },
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / "candidate_v6"
    path.mkdir(parents=True, exist_ok=True)
    return path / "candidate_v6_gated_research_report.json"


def _coverage_improvement_path() -> Path:
    return _output_dir() / "diagnostics" / "data_source_coverage_improvement.json"


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


def _safe_float(value: Any) -> float:
    try:
        parsed = float(value or 0.0)
    except Exception:
        return 0.0
    return parsed


def _finite_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def _horizon_days(horizon: str) -> int:
    try:
        return max(1, int(str(horizon).lower().replace("d", "")))
    except Exception:
        return 1


def _normalise_horizons(horizons: Iterable[str]) -> tuple[str, ...]:
    values = tuple(str(item) for item in horizons)
    return values or DEFAULT_HORIZONS


def _feature_store_from_report(report: Mapping[str, Any]) -> Mapping[str, Any]:
    feature_store = report.get("feature_store_v6")
    if not isinstance(feature_store, Mapping):
        feature_store = report.get("feature_store_v5")
    return feature_store if isinstance(feature_store, Mapping) else {}


def _positive_delta_groups(report: Mapping[str, Any]) -> list[str]:
    delta = report.get("feature_coverage_delta") if isinstance(report.get("feature_coverage_delta"), Mapping) else {}
    groups: list[str] = []
    for group in FACTOR_GROUP_FIELDS:
        payload = delta.get(group) if isinstance(delta, Mapping) else None
        if isinstance(payload, Mapping) and _safe_float(payload.get("delta")) > 0.0:
            groups.append(group)
    return groups


def _fields_by_group(usable_fields: Iterable[Any]) -> dict[str, list[str]]:
    usable = {str(item) for item in usable_fields}
    return {
        group: sorted(usable.intersection(fields))
        for group, fields in FACTOR_GROUP_FIELDS.items()
    }


def _uses_mock_or_sample(payload: Mapping[str, Any]) -> bool:
    if payload.get("sample_data_used") or payload.get("mock_data_used") or payload.get("baseline_used"):
        return True
    source_quality = payload.get("source_quality")
    if not isinstance(source_quality, Mapping):
        return False
    for item in source_quality.values():
        if isinstance(item, Mapping) and (item.get("sample_data_used") or item.get("mock_data_used") or item.get("status") in {"sample_data", "mock_data"}):
            return True
    return False


def _get_candidate_v6_readiness() -> dict[str, Any]:
    # Lazy import avoids a module cycle: readiness service imports FACTOR_GROUP_FIELDS from here.
    from .real_data_coverage_validation_service import get_candidate_v6_readiness

    payload = get_candidate_v6_readiness()
    return dict(payload) if isinstance(payload, Mapping) else {}


def _base_admission(report: Mapping[str, Any]) -> dict[str, Any]:
    blocked: list[str] = []
    feature_store = _feature_store_from_report(report)
    usable_fields = list(feature_store.get("usable_fields") or [])
    fields_by_group = _fields_by_group(usable_fields)
    positive_groups = _positive_delta_groups(report)
    positive_groups_with_fields = [group for group in positive_groups if fields_by_group.get(group)]
    new_fields = sorted({field for group in positive_groups_with_fields for field in fields_by_group.get(group, [])})

    if not isinstance(report, Mapping) or not report:
        blocked.append("missing_data_source_coverage_improvement_report")
    if not positive_groups:
        blocked.append("feature_coverage_delta_empty")
    if not positive_groups_with_fields:
        blocked.append("new_real_factor_group_missing")
    if _uses_mock_or_sample(feature_store):
        blocked.append("sample_or_mock_data_detected")
    if feature_store and not bool(feature_store.get("leakage_check_pass", True)):
        blocked.append("feature_store_leakage_failed")

    return {
        "eligible": False,
        "stage": "coverage",
        "candidate_version": "v6",
        "required_factor_groups": list(FACTOR_GROUP_FIELDS),
        "positive_delta_groups": positive_groups,
        "available_factor_groups": [group for group, fields in fields_by_group.items() if fields],
        "new_factor_groups": positive_groups_with_fields,
        "new_fields": new_fields,
        "blocked_reasons": blocked,
        "feature_store_sample_or_mock_used": _uses_mock_or_sample(feature_store),
    }


def _readiness_admission(readiness: Mapping[str, Any]) -> dict[str, Any]:
    blocked: list[str] = []
    status = str(readiness.get("status") or "").lower()
    ready_flag = bool(readiness.get("ready", status == "ready"))
    new_factor_groups = [str(item) for item in readiness.get("new_factor_groups") or []]
    new_fields = [str(item) for item in readiness.get("new_fields") or []]

    if not readiness:
        blocked.append("candidate_v6_readiness_missing")
    if status != "ready" or not ready_flag:
        blocked.append("candidate_v6_readiness_not_ready")
        blocked.extend(str(item) for item in readiness.get("blocked_reasons") or [])
    if not new_factor_groups:
        blocked.append("new_real_factor_group_missing")
    if not new_fields:
        blocked.append("feature_store_v6_real_new_fields_missing")
    if readiness.get("sample_data_used") or readiness.get("mock_data_used") or readiness.get("baseline_used"):
        blocked.append("sample_or_mock_data_detected")
    if not bool(readiness.get("no_lookahead_pass")):
        blocked.append("feature_store_no_lookahead_failed")
    if not bool(readiness.get("feature_store_leakage_check_pass", True)):
        blocked.append("feature_store_leakage_failed")

    return {
        "stage": "candidate_v6_readiness",
        "readiness_status": status or "missing",
        "readiness_ready": bool(status == "ready" and ready_flag),
        "new_factor_groups": sorted(set(new_factor_groups)),
        "new_fields": sorted(set(new_fields)),
        "blocked_reasons": sorted(set(blocked)),
    }


def _feature_stability_admission(evidence: Mapping[str, Any]) -> dict[str, Any]:
    blocked: list[str] = []
    status = str(evidence.get("evidence_status") or "").lower()
    score = _finite_float(evidence.get("stability_score"))

    if not evidence or status in {"", "missing"}:
        blocked.append("feature_stability_evidence_missing")
    elif status not in {"success", "available"}:
        blocked.append("feature_stability_evidence_unavailable")
    if evidence and score is None:
        blocked.append("feature_stability_score_missing")

    return {
        "stage": "feature_stability",
        "feature_stability_evidence_status": status or "missing",
        "feature_stability_score": score,
        "feature_stability_passed": bool(evidence.get("passed")),
        "blocked_reasons": sorted(set(blocked)),
    }


def _merge_pretraining_admission(
    coverage: Mapping[str, Any],
    readiness: Mapping[str, Any],
    feature_stability: Mapping[str, Any],
) -> dict[str, Any]:
    blocked = sorted(
        set(
            str(item)
            for item in (
                list(coverage.get("blocked_reasons") or [])
                + list(readiness.get("blocked_reasons") or [])
                + list(feature_stability.get("blocked_reasons") or [])
            )
        )
    )
    readiness_ready = bool(readiness.get("readiness_ready"))
    readiness_has_increment = bool(readiness.get("new_factor_groups")) and bool(readiness.get("new_fields"))
    if readiness_ready and readiness_has_increment:
        readiness_canonical_blockers = {
            "missing_data_source_coverage_improvement_report",
            "feature_coverage_delta_empty",
            "new_real_factor_group_missing",
        }
        blocked = [reason for reason in blocked if reason not in readiness_canonical_blockers]
    new_factor_groups = sorted(
        set(str(item) for item in list(coverage.get("new_factor_groups") or []) + list(readiness.get("new_factor_groups") or []))
    )
    new_fields = sorted(set(str(item) for item in list(coverage.get("new_fields") or []) + list(readiness.get("new_fields") or [])))
    return {
        **dict(coverage),
        "stage": "pre_training_gates",
        "eligible": not blocked,
        "new_factor_groups": new_factor_groups,
        "new_fields": new_fields,
        "blocked_reasons": blocked,
        "candidate_v6_readiness_status": readiness.get("readiness_status"),
        "candidate_v6_readiness_ready": bool(readiness.get("readiness_ready")),
        "feature_stability_evidence_status": feature_stability.get("feature_stability_evidence_status"),
        "feature_stability_score": feature_stability.get("feature_stability_score"),
        "feature_stability_passed": bool(feature_stability.get("feature_stability_passed")),
        "pretraining_gate_details": {
            "coverage": dict(coverage),
            "candidate_v6_readiness": dict(readiness),
            "feature_stability": dict(feature_stability),
        },
    }


def _with_dataset_gate(admission: Mapping[str, Any], dataset: Mapping[str, Any]) -> dict[str, Any]:
    blocked = list(admission.get("blocked_reasons") or [])
    if dataset.get("status") != "success":
        blocked.append("training_dataset_v6_not_success")
    if not bool(dataset.get("leakage_check_pass")):
        blocked.append("training_dataset_v6_leakage_failed")
    if dataset.get("sample_data_used") or dataset.get("mock_data_used") or dataset.get("baseline_used"):
        blocked.append("training_dataset_v6_sample_or_mock_detected")
    return {
        **dict(admission),
        "stage": "training_dataset",
        "eligible": not blocked,
        "blocked_reasons": sorted(set(blocked)),
        "training_dataset_status": dataset.get("status"),
        "training_dataset_leakage_pass": bool(dataset.get("leakage_check_pass")),
        "training_dataset_feature_count": len(dataset.get("feature_cols") or []),
    }


def _high_confidence_summary(oof_integrity: Mapping[str, Any]) -> dict[str, Any]:
    horizons = oof_integrity.get("horizons") if isinstance(oof_integrity.get("horizons"), Mapping) else {}
    summary: dict[str, Any] = {}
    for horizon, payload in horizons.items():
        if not isinstance(payload, Mapping):
            continue
        subsets = payload.get("confidence_subset") if isinstance(payload.get("confidence_subset"), Mapping) else {}
        top10 = subsets.get("top_10pct") if isinstance(subsets.get("top_10pct"), Mapping) else {}
        top20 = subsets.get("top_20pct") if isinstance(subsets.get("top_20pct"), Mapping) else {}
        summary[str(horizon)] = {
            "top10": {
                "sample_count": top10.get("sample_count"),
                "direction_accuracy": top10.get("direction_accuracy"),
                "cost_adjusted_expectancy": top10.get("cost_adjusted_expectancy"),
                "max_drawdown_proxy": top10.get("max_drawdown_proxy"),
            },
            "top20": {
                "sample_count": top20.get("sample_count"),
                "direction_accuracy": top20.get("direction_accuracy"),
                "cost_adjusted_expectancy": top20.get("cost_adjusted_expectancy"),
                "max_drawdown_proxy": top20.get("max_drawdown_proxy"),
            },
        }
    return sanitize_for_json(summary)


def _blocked_result(
    admission: Mapping[str, Any],
    *,
    horizons: tuple[str, ...],
    dataset: Mapping[str, Any] | None = None,
    readiness: Mapping[str, Any] | None = None,
    feature_stability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    report = {
        "status": "blocked",
        "generated_at": _now(),
        "report_path": str(_report_path()),
        "candidate_version": "v6",
        "dataset_version": V6_DATASET_VERSION,
        "feature_store_version": V6_FEATURE_STORE_VERSION,
        "feature_set": V6_FEATURE_SET,
        "horizons": horizons,
        "v6_admission": dict(admission),
        "candidate_v6_readiness": dict(readiness or {}),
        "feature_stability_evidence": dict(feature_stability or {}),
        "blocked_reasons": list(admission.get("blocked_reasons") or []),
        "blocking_reasons": list(admission.get("blocked_reasons") or []),
        "new_fields": list(admission.get("new_fields") or []),
        "training_dataset": dict(dataset or {}),
        "candidate": {"status": "not_run"},
        "oof_integrity": {"status": "not_run"},
        "research_backtest": {"status": "not_run"},
        "institutional_validation": {"status": "not_run"},
        "promotion_dry_run": {"status": "not_run"},
        "candidate_metrics": {},
        "gate_passed": False,
        "manual_approval_recommended": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "message": "candidate_v6 admission blocked; no training was run.",
    }
    _write_json(_report_path(), report)
    return sanitize_for_json(report)


def run_candidate_v6_gated_research(*, horizons: Iterable[str] = DEFAULT_HORIZONS) -> dict[str, Any]:
    """Train candidate_v6 only after readiness, evidence, and dataset gates pass."""

    horizon_list = _normalise_horizons(horizons)
    coverage_report = _read_json(_coverage_improvement_path())
    coverage_report = coverage_report if isinstance(coverage_report, Mapping) else {}
    coverage_admission = _base_admission(coverage_report)
    readiness = _get_candidate_v6_readiness()
    feature_stability = get_feature_stability_evidence(candidate_version="v5")
    feature_stability = feature_stability if isinstance(feature_stability, Mapping) else {}
    admission = _merge_pretraining_admission(
        coverage_admission,
        _readiness_admission(readiness),
        _feature_stability_admission(feature_stability),
    )
    if admission["blocked_reasons"]:
        return _blocked_result(admission, horizons=horizon_list, readiness=readiness, feature_stability=feature_stability)

    dataset = build_training_dataset(
        horizons=tuple(_horizon_days(item) for item in horizon_list),
        dataset_version=V6_DATASET_VERSION,
        feature_store_version=V6_FEATURE_STORE_VERSION,
        feature_set=V6_FEATURE_SET,
    )
    dataset = dataset if isinstance(dataset, Mapping) else {"status": "failed"}
    admission = _with_dataset_gate(admission, dataset)
    if not admission["eligible"]:
        return _blocked_result(admission, horizons=horizon_list, dataset=dataset, readiness=readiness, feature_stability=feature_stability)

    candidate = run_candidate_training(
        horizons=horizon_list,
        candidate_version="v6",
        dataset_version=V6_DATASET_VERSION,
        feature_set=V6_FEATURE_SET,
        label_variants=V6_LABEL_VARIANTS,
        models=V6_MODELS,
        calibration=V6_CALIBRATION,
        no_trade_filters=V6_NO_TRADE_FILTERS,
    )
    oof_integrity = get_oof_integrity_report(candidate_version="v6", dataset_version="v6")
    high_confidence = _high_confidence_summary(oof_integrity if isinstance(oof_integrity, Mapping) else {})
    research_backtest = run_research_backtest(candidate_version="v6", horizons=horizon_list)
    institutional_validation = run_institutional_validation(candidate_version="v6", dry_run=True)
    promotion_dry_run = promote_candidate(candidate_version="v6", dry_run=True)
    archive = archive_research_run(
        candidate_version="v6",
        extra_payload={
            "candidate_status": candidate.get("status") if isinstance(candidate, Mapping) else "unknown",
            "admission": admission,
            "institutional_validation_status": institutional_validation.get("status") if isinstance(institutional_validation, Mapping) else "unknown",
            "promotion_dry_run_status": promotion_dry_run.get("status") if isinstance(promotion_dry_run, Mapping) else "unknown",
        },
    )

    candidate_metrics = dict(candidate.get("metrics_by_horizon") or {}) if isinstance(candidate, Mapping) else {}
    validation_passed = bool(institutional_validation.get("passed")) if isinstance(institutional_validation, Mapping) else False
    promotion_passed = bool(promotion_dry_run.get("passed")) if isinstance(promotion_dry_run, Mapping) else False
    report = {
        "status": "success" if isinstance(candidate, Mapping) and candidate.get("status") == "success" else "failed",
        "generated_at": _now(),
        "report_path": str(_report_path()),
        "candidate_version": "v6",
        "dataset_version": V6_DATASET_VERSION,
        "feature_store_version": V6_FEATURE_STORE_VERSION,
        "feature_set": V6_FEATURE_SET,
        "horizons": horizon_list,
        "v6_admission": admission,
        "candidate_v6_readiness": dict(readiness),
        "feature_stability_evidence": dict(feature_stability),
        "new_fields": list(admission.get("new_fields") or []),
        "training_dataset": dict(dataset),
        "candidate": candidate,
        "candidate_metrics": candidate_metrics,
        "oof_integrity": oof_integrity,
        "high_confidence": high_confidence,
        "research_backtest": research_backtest,
        "institutional_validation": institutional_validation,
        "promotion_dry_run": promotion_dry_run,
        "gate_passed": bool(validation_passed and promotion_passed),
        "manual_approval_recommended": bool(validation_passed and promotion_passed),
        "artifact_dir": archive.get("artifact_dir") if isinstance(archive, Mapping) else "",
        "artifact_run_id": archive.get("run_id") if isinstance(archive, Mapping) else "",
        "training_invoked": True,
        "active_updated": False,
        "customer_prediction_generated": False,
        "message": "candidate_v6 research pipeline completed without publishing active or generating customer predictions.",
    }
    _write_json(_report_path(), report)
    return sanitize_for_json(report)
