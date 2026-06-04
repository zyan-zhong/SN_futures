from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


MONITORING_SPEC_VERSION = "post_release_monitoring_spec_v1"
REPORT_FILENAME = "post_release_monitoring_spec_report.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _path(relative_path: str) -> Path:
    primary = _output_dir() / relative_path
    if primary.exists():
        return primary
    fallback = Path("outputs") / relative_path
    if fallback.exists():
        return fallback
    return primary


def _paths() -> dict[str, Path]:
    return {
        "decision_board": _path("model_research/research_decision_board.json"),
        "shadow_replay": _path("model_research/shadow_replay_report.json"),
        "shadow_mode_readiness": _path("model_research/shadow_mode_readiness_spec.json"),
        "shadow_output_contract": _path("model_research/shadow_output_contract_report.json"),
        "data_quality": _path("diagnostics/managed_data_quality_scorecard.json"),
        "evidence_freshness": _path("model_research/evidence_freshness_report.json"),
        "cost_stress_attribution": _path("model_research/cost_stress_attribution.json"),
        "year_concentration": _path("model_research/year_concentration_evidence.json"),
        "production_cutover": _path("model_research/production_cutover_checklist_report.json"),
        "registry_safety": _path("model_research/model_registry_safety_report.json"),
    }


def _safe_payload(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = _safe_payload(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _status(payload: Mapping[str, Any]) -> str:
    return str(payload.get("status") or "missing").lower()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _active_model_paths() -> list[Path]:
    out = _output_dir()
    cwd = Path.cwd()
    return [
        out / "model_registry" / "active_model.json",
        out / "models" / "active_model.json",
        cwd / "outputs" / "model_registry" / "active_model.json",
        cwd / "outputs" / "models" / "active_model.json",
    ]


def _customer_prediction_paths() -> list[Path]:
    out = _output_dir()
    cwd = Path.cwd()
    return [
        out / "customer_predictions",
        out / "customer_predictions.json",
        out.parent / "customer_predictions",
        cwd / "outputs" / "customer_predictions",
        cwd / "outputs" / "customer_predictions.json",
        cwd / "app_data" / "customer_predictions",
    ]


def _existing(paths: Sequence[Path]) -> list[str]:
    return [str(path) for path in paths if path.exists()]


def _sentinel(
    sentinel_id: str,
    *,
    category: str,
    source: str,
    threshold_key: str,
    action: str,
    severity: str = "warning",
) -> dict[str, Any]:
    return {
        "id": sentinel_id,
        "category": category,
        "source": source,
        "threshold_key": threshold_key,
        "severity": severity,
        "action": action,
        "enabled_in_planning": True,
        "live_monitoring_enabled": False,
    }


def define_data_drift_sentinels() -> list[dict[str, Any]]:
    return [
        _sentinel(
            "managed_field_missing_rate_drift",
            category="data",
            source="managed_data_quality",
            threshold_key="required_managed_field_missing_rate",
            action="block_live_monitoring_and_refresh_managed_data_quality",
        ),
        _sentinel(
            "basis_distribution_drift",
            category="data",
            source="feature_store_or_managed_proxy",
            threshold_key="basis_zscore_drift",
            action="review_basis_source_and_managed_proxy_schema",
        ),
        _sentinel(
            "inventory_distribution_drift",
            category="data",
            source="feature_store_or_managed_proxy",
            threshold_key="inventory_zscore_drift",
            action="review_inventory_source_quality",
        ),
        _sentinel(
            "regime_distribution_drift",
            category="data",
            source="year_concentration_and_shadow_replay",
            threshold_key="regime_distribution_drift",
            action="review_regime_coverage_before_shadow_or_live_use",
        ),
    ]


def define_prediction_drift_sentinels() -> list[dict[str, Any]]:
    return [
        _sentinel(
            "signal_flip_drift",
            category="prediction",
            source="shadow_replay",
            threshold_key="signal_flip_rate",
            action="investigate_shadow_signal_instability",
        ),
        _sentinel(
            "confidence_drift",
            category="prediction",
            source="shadow_replay",
            threshold_key="confidence_distribution_drift",
            action="review_confidence_calibration",
        ),
        _sentinel(
            "horizon_exposure_drift",
            category="prediction",
            source="shadow_replay",
            threshold_key="horizon_exposure_drift",
            action="review_horizon_exposure",
        ),
        _sentinel(
            "turnover_drift",
            category="prediction",
            source="shadow_replay_or_future_live_monitoring",
            threshold_key="turnover_drift",
            action="review_turnover_and_cost_pressure",
        ),
        _sentinel(
            "customer_prediction_path_violation",
            category="artifact_boundary",
            source="filesystem",
            threshold_key="customer_predictions_path_exists_unexpectedly",
            action="enter_governance_lockdown_and_remove_unapproved_customer_outputs",
            severity="critical",
        ),
        _sentinel(
            "active_model_unexpected_existence",
            category="artifact_boundary",
            source="filesystem",
            threshold_key="active_model_json_exists_unexpectedly",
            action="enter_governance_lockdown_and_review_registry_safety",
            severity="critical",
        ),
        _sentinel(
            "shadow_output_path_collision",
            category="artifact_boundary",
            source="shadow_output_contract",
            threshold_key="shadow_output_path_collision",
            action="block_shadow_output_until_path_isolation_passes",
            severity="critical",
        ),
    ]


def define_cost_drift_sentinels() -> list[dict[str, Any]]:
    return [
        _sentinel(
            "cost_drag_drift",
            category="cost",
            source="cost_stress_attribution",
            threshold_key="cost_drag_drift",
            action="review_cost_drag_before_shadow_or_live_use",
        ),
        _sentinel(
            "two_x_cost_expectancy_negative",
            category="cost",
            source="cost_stress_attribution",
            threshold_key="two_x_cost_expectancy_below_zero",
            action="block_live_monitoring_until_2x_cost_is_non_negative",
            severity="critical",
        ),
        _sentinel(
            "three_x_cost_expectancy_negative",
            category="cost",
            source="cost_stress_attribution",
            threshold_key="three_x_cost_expectancy_below_zero",
            action="block_live_monitoring_until_3x_cost_is_acceptable",
            severity="critical",
        ),
    ]


def define_pit_regression_sentinels() -> list[dict[str, Any]]:
    return [
        _sentinel(
            "pit_timestamp_regression",
            category="pit",
            source="pit_replay_and_managed_data_audit",
            threshold_key="pit_replay_failure",
            action="block_feature_store_build_and_live_monitoring",
            severity="critical",
        ),
        _sentinel(
            "stale_evidence_regression",
            category="freshness",
            source="evidence_freshness",
            threshold_key="evidence_freshness_fail",
            action="refresh_evidence_before_manual_review",
            severity="critical",
        ),
    ]


def _alert_threshold(
    label: str,
    *,
    threshold: str,
    rationale: str,
    action: str,
) -> dict[str, Any]:
    return {"threshold": threshold, "rationale": rationale, "action": action}


def _build_alert_thresholds() -> dict[str, dict[str, Any]]:
    return {
        "required_managed_field_missing_rate": _alert_threshold(
            "required_managed_field_missing_rate",
            threshold="> 0.05",
            rationale="A required managed field missing-rate above 5% can invalidate v12 feature joins.",
            action="block live monitoring and refresh managed data quality.",
        ),
        "basis_zscore_drift": _alert_threshold(
            "basis_zscore_drift",
            threshold="abs(zscore) > 3.0",
            rationale="Basis distribution drift can indicate source schema drift or market regime change.",
            action="review basis source and schema mapping.",
        ),
        "inventory_zscore_drift": _alert_threshold(
            "inventory_zscore_drift",
            threshold="abs(zscore) > 3.0",
            rationale="Inventory drift can indicate missing/invalid warehouse or LME inventory data.",
            action="review inventory source quality.",
        ),
        "regime_distribution_drift": _alert_threshold(
            "regime_distribution_drift",
            threshold="PSI > 0.20 or any regime share delta > 0.25",
            rationale="Regime imbalance was a prior validation blocker.",
            action="review regime exposure before shadow or live use.",
        ),
        "signal_flip_rate": _alert_threshold(
            "signal_flip_rate",
            threshold="> 0.35",
            rationale="Frequent shadow signal flips can increase cost drag and operational noise.",
            action="investigate unstable periods and cost guards.",
        ),
        "confidence_distribution_drift": _alert_threshold(
            "confidence_distribution_drift",
            threshold="KS statistic > 0.20 or median shift > 0.15",
            rationale="Confidence drift can invalidate calibrated threshold assumptions.",
            action="review calibration evidence.",
        ),
        "horizon_exposure_drift": _alert_threshold(
            "horizon_exposure_drift",
            threshold="any horizon share delta > 0.20",
            rationale="Horizon exposure drift can reintroduce concentration and cost failures.",
            action="review horizon gating.",
        ),
        "turnover_drift": _alert_threshold(
            "turnover_drift",
            threshold="> 2x research turnover baseline",
            rationale="Turnover drift can turn positive research expectancy negative after costs.",
            action="review cost pressure and no-trade filters.",
        ),
        "two_x_cost_expectancy_below_zero": _alert_threshold(
            "two_x_cost_expectancy_below_zero",
            threshold="< 0",
            rationale="2x cost stress must remain non-negative before live monitoring is useful.",
            action="block live monitoring and review cost attribution.",
        ),
        "three_x_cost_expectancy_below_zero": _alert_threshold(
            "three_x_cost_expectancy_below_zero",
            threshold="< 0",
            rationale="3x cost stress below zero indicates fragile cost resilience.",
            action="block live monitoring and review cost attribution.",
        ),
        "pit_replay_failure": _alert_threshold(
            "pit_replay_failure",
            threshold="any PIT replay fail",
            rationale="Point-in-time regression can create lookahead leakage.",
            action="block v12 builds and live monitoring.",
        ),
        "evidence_freshness_fail": _alert_threshold(
            "evidence_freshness_fail",
            threshold="freshness status in fail/blocked/stale",
            rationale="Stale reports must not be used for approval or live monitoring.",
            action="refresh evidence bundle and decision board.",
        ),
        "customer_predictions_path_exists_unexpectedly": _alert_threshold(
            "customer_predictions_path_exists_unexpectedly",
            threshold="path exists without approval",
            rationale="Customer predictions are forbidden in the current research-only state.",
            action="enter lockdown and remove unapproved output.",
        ),
        "active_model_json_exists_unexpectedly": _alert_threshold(
            "active_model_json_exists_unexpectedly",
            threshold="active_model.json exists without approval",
            rationale="Unexpected active model indicates registry safety violation.",
            action="enter lockdown and review registry safety.",
        ),
        "shadow_output_path_collision": _alert_threshold(
            "shadow_output_path_collision",
            threshold="any shadow output under customer_predictions or active model path",
            rationale="Shadow outputs must remain isolated from customer-facing outputs.",
            action="block shadow output and fix path contract.",
        ),
    }


def _sentinel_ids(items: Sequence[Mapping[str, Any]]) -> set[str]:
    return {str(item.get("id") or "") for item in items if item.get("id")}


def validate_monitoring_spec_completeness(spec: Mapping[str, Any]) -> dict[str, Any]:
    data_ids = _sentinel_ids(spec.get("data_drift_sentinels") if isinstance(spec.get("data_drift_sentinels"), list) else [])
    prediction_ids = _sentinel_ids(spec.get("prediction_drift_sentinels") if isinstance(spec.get("prediction_drift_sentinels"), list) else [])
    cost_ids = _sentinel_ids(spec.get("cost_drift_sentinels") if isinstance(spec.get("cost_drift_sentinels"), list) else [])
    pit_ids = _sentinel_ids(spec.get("pit_regression_sentinels") if isinstance(spec.get("pit_regression_sentinels"), list) else [])
    blocking: list[str] = []
    if "pit_timestamp_regression" not in pit_ids:
        blocking.append("pit_timestamp_regression_sentinel_missing")
    if not {"cost_drag_drift", "two_x_cost_expectancy_negative", "three_x_cost_expectancy_negative"}.issubset(cost_ids):
        blocking.append("cost_drift_sentinel_missing")
    if "customer_prediction_path_violation" not in prediction_ids:
        blocking.append("customer_prediction_path_sentinel_missing")
    if "active_model_unexpected_existence" not in prediction_ids:
        blocking.append("active_model_unexpected_existence_sentinel_missing")
    if "shadow_output_path_collision" not in prediction_ids:
        blocking.append("shadow_output_path_collision_sentinel_missing")
    if "managed_field_missing_rate_drift" not in data_ids:
        blocking.append("managed_field_missing_rate_sentinel_missing")
    return _safe_payload(
        {
            "status": "pass" if not blocking else "fail",
            "blocking_reasons": blocking,
        }
    )


def _load_evidence() -> dict[str, dict[str, Any]]:
    return {name: _read_json(path) for name, path in _paths().items()}


def _shadow_vs_live_metrics(shadow_replay: Mapping[str, Any], blockers: Sequence[str]) -> dict[str, Any]:
    stability = shadow_replay.get("stability_metrics") if isinstance(shadow_replay.get("stability_metrics"), Mapping) else {}
    return _safe_payload(
        {
            "shadow_signal_distribution": {
                "horizon_distribution": stability.get("horizon_distribution", {}),
                "regime_distribution": stability.get("regime_distribution", {}),
                "signal_flip_rate": stability.get("signal_flip_rate"),
            },
            "live_signal_distribution_placeholder": {},
            "shadow_vs_live_enabled": False,
            "enablement_blockers": list(blockers),
        }
    )


def _planning_gaps(
    *,
    active_model_present: bool,
    customer_prediction_paths_present: bool,
    evidence: Mapping[str, Mapping[str, Any]],
) -> tuple[list[str], list[str], list[str]]:
    gaps: list[str] = []
    warnings: list[str] = []
    blocking: list[str] = []
    board = evidence.get("decision_board", {})
    shadow = evidence.get("shadow_mode_readiness", {})
    shadow_replay = evidence.get("shadow_replay", {})
    data_quality = evidence.get("data_quality", {})
    freshness = evidence.get("evidence_freshness", {})
    shadow_contract = evidence.get("shadow_output_contract", {})

    if not active_model_present:
        gaps.append("active_model_missing")
    if not bool(board.get("manual_approval_recommended")):
        gaps.append("manual_approval_missing")
    if _status(shadow) in {"missing", "blocked", "fail", "failed"} or not bool(shadow.get("shadow_mode_allowed")):
        gaps.append("shadow_readiness_blocked")
    if not shadow_replay:
        gaps.append("shadow_replay_report_missing")
        warnings.append("shadow_replay_report_missing")
    if not data_quality:
        gaps.append("data_quality_report_missing")
        warnings.append("data_quality_report_missing")
    if _status(freshness) in {"missing", "blocked", "fail", "failed", "stale"}:
        gaps.append("evidence_freshness_not_pass")
        warnings.append("evidence_freshness_not_pass")
    if _status(shadow_contract) in {"missing", "blocked", "fail", "failed"}:
        gaps.append("shadow_output_contract_not_pass")
        warnings.append("shadow_output_contract_not_pass")
    if active_model_present:
        blocking.append("active_model_unexpected_exists")
    if customer_prediction_paths_present:
        blocking.append("customer_prediction_path_unexpected_exists")
    return list(dict.fromkeys(gaps)), list(dict.fromkeys(warnings)), list(dict.fromkeys(blocking))


def build_monitoring_spec_report(*, write: bool = True, record_run: bool = True) -> dict[str, Any]:
    evidence = _load_evidence()
    active_model_paths = _existing(_active_model_paths())
    customer_prediction_paths = _existing(_customer_prediction_paths())
    active_model_present = bool(active_model_paths)
    customer_prediction_paths_present = bool(customer_prediction_paths)
    data_drift = define_data_drift_sentinels()
    prediction_drift = define_prediction_drift_sentinels()
    cost_drift = define_cost_drift_sentinels()
    pit_regression = define_pit_regression_sentinels()
    shadow_replay = evidence.get("shadow_replay", {})
    board = evidence.get("decision_board", {})
    gaps, warnings, blocking = _planning_gaps(
        active_model_present=active_model_present,
        customer_prediction_paths_present=customer_prediction_paths_present,
        evidence=evidence,
    )
    spec_shell = {
        "data_drift_sentinels": data_drift,
        "prediction_drift_sentinels": prediction_drift,
        "cost_drift_sentinels": cost_drift,
        "pit_regression_sentinels": pit_regression,
    }
    completeness = validate_monitoring_spec_completeness(spec_shell)
    blocking.extend(completeness.get("blocking_reasons") or [])
    sentinel_count = sum(len(items) for items in (data_drift, prediction_drift, cost_drift, pit_regression))
    alert_thresholds = _build_alert_thresholds()
    live_blockers = list(dict.fromkeys(gaps + blocking))
    shadow_vs_live = _shadow_vs_live_metrics(shadow_replay, live_blockers)
    live_monitoring_enabled = bool(
        active_model_present
        and bool(board.get("manual_approval_recommended"))
        and not live_blockers
        and _status(evidence.get("shadow_mode_readiness", {})) in {"ready", "pass", "success"}
    )
    status = "blocked" if blocking or completeness.get("status") != "pass" else "planning_only"
    report = {
        "status": status,
        "generated_at": _now(),
        "monitoring_spec_version": MONITORING_SPEC_VERSION,
        "monitoring_mode": "planning_only",
        "live_monitoring_enabled": live_monitoring_enabled,
        "active_model_present": active_model_present,
        "active_model_paths": active_model_paths,
        "customer_prediction_paths_present": customer_prediction_paths_present,
        "customer_prediction_paths": customer_prediction_paths,
        "shadow_replay_status": shadow_replay.get("status", "missing"),
        "shadow_replay_source_candidate": shadow_replay.get("source_candidate_version", ""),
        "data_drift_sentinels": data_drift,
        "prediction_drift_sentinels": prediction_drift,
        "cost_drift_sentinels": cost_drift,
        "pit_regression_sentinels": pit_regression,
        "shadow_vs_live_comparison_metrics": shadow_vs_live,
        "alert_thresholds": alert_thresholds,
        "sentinel_count": sentinel_count,
        "active_customer_prediction_sentinel_status": "blocked" if active_model_present or customer_prediction_paths_present else "pass",
        "escalation_policy": [
            "Do not deploy monitoring daemon until active/shadow gates are approved.",
            "If active_model.json or customer_predictions appears unexpectedly, enter governance lockdown.",
            "If PIT replay or evidence freshness fails, block cutover and refresh governance evidence.",
            "If cost stress expectancy falls below zero, stop live monitoring review and refresh cost attribution.",
        ],
        "readiness_gaps": live_blockers,
        "blocking_reasons": list(dict.fromkeys(blocking)),
        "warning_reasons": list(dict.fromkeys(warnings)),
        "source_reports": {
            name: {"path": str(_paths()[name]), "status": payload.get("status", "missing") if payload else "missing"}
            for name, payload in evidence.items()
        },
        "decision_board_active_publish_allowed": bool(board.get("active_publish_allowed")),
        "monitoring_daemon_started": False,
        "monitoring_deployed": False,
        "oof_generated": False,
        "feature_store_v12_built": False,
        "training_dataset_v12_built": False,
        "candidate_or_promotion_invoked": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    safe = _safe_payload(report)
    if write:
        _write_json(_report_path(), safe)
    if record_run:
        run = start_research_run(
            service_name="post_release_monitoring_spec",
            run_type="report_write",
            input_paths=[str(path) for path in _paths().values() if path.exists()],
            output_paths=[str(_report_path())],
        )
        append_run_ledger(finalize_research_run(run, error_summary="artifact boundary violation" if blocking else ""))
    return safe


def build_post_release_monitoring_spec() -> dict[str, Any]:
    return build_monitoring_spec_report(write=True, record_run=True)


def get_post_release_monitoring_spec() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if payload:
        return _safe_payload(payload)
    return build_monitoring_spec_report(write=False, record_run=False)

