from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_text
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


DRILL_VERSION = "incident_drill_v1"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / "incident_drill_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _json_compatible(payload: Any) -> Any:
    try:
        return json.loads(json.dumps(payload, ensure_ascii=False, default=str))
    except Exception:
        return str(payload)


def _scrub_payload(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {sanitize_text(str(key)): _scrub_payload(value) for key, value in payload.items()}
    if isinstance(payload, list):
        return [_scrub_payload(item) for item in payload]
    if isinstance(payload, str):
        return sanitize_text(payload)
    return payload


def _safe_payload(payload: Any) -> Any:
    return _scrub_payload(_json_compatible(payload))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return dict(payload) if isinstance(payload, Mapping) else {}


def _scenario(
    scenario: str,
    reason: str,
    *,
    signal: str,
    expected_lockdown: bool = True,
) -> dict[str, Any]:
    return _safe_payload(
        {
            "scenario": scenario,
            "status": "pass" if expected_lockdown else "not_triggered",
            "lockdown_triggered": bool(expected_lockdown),
            "lockdown_reason": reason if expected_lockdown else "",
            "signal": signal,
            "simulated_artifact_created": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def simulate_secret_leak_detection() -> dict[str, Any]:
    return _scenario(
        "secret_leak_detected",
        "secret_leak_detected",
        signal="runtime secret scan finding_count > 0",
    )


def simulate_endpoint_token_echo() -> dict[str, Any]:
    return _scenario(
        "endpoint_echoed_token",
        "endpoint_echoed_token",
        signal="provider response echoed credential material, redacted before reporting",
    )


def simulate_unapproved_active_model() -> dict[str, Any]:
    return _scenario(
        "unauthorized_active_model_detected",
        "unauthorized_active_model_detected",
        signal="unexpected active model file path detected in output inventory",
    )


def simulate_unapproved_customer_predictions() -> dict[str, Any]:
    return _scenario(
        "unauthorized_customer_prediction_detected",
        "unauthorized_customer_prediction_detected",
        signal="unexpected customer prediction output path detected in output inventory",
    )


def simulate_forbidden_action_exposure() -> dict[str, Any]:
    return _scenario(
        "forbidden_api_action_exposed",
        "forbidden_api_action_exposed",
        signal="governance access-control UI/API violation count > 0",
    )


def simulate_schema_drift_after_ready() -> dict[str, Any]:
    return _scenario(
        "schema_drift_after_ready",
        "schema_drift_after_ready",
        signal="managed proxy schema changed after a previous ready state",
    )


def simulate_data_quality_gate_failed_after_ready() -> dict[str, Any]:
    return _scenario(
        "data_quality_gate_failed_after_ready",
        "data_quality_gate_failed_after_ready",
        signal="managed data quality gate failed after a previous ready state",
    )


def simulate_stale_evidence_used_for_approval() -> dict[str, Any]:
    return _scenario(
        "stale_evidence_used_for_approval",
        "stale_evidence_used_for_approval",
        signal="stale evidence was present during an approval attempt",
    )


def _simulation_scenarios() -> list[dict[str, Any]]:
    return [
        simulate_secret_leak_detection(),
        simulate_endpoint_token_echo(),
        simulate_unapproved_active_model(),
        simulate_unapproved_customer_predictions(),
        simulate_forbidden_action_exposure(),
        simulate_schema_drift_after_ready(),
        simulate_data_quality_gate_failed_after_ready(),
        simulate_stale_evidence_used_for_approval(),
    ]


def _active_model_paths() -> list[Path]:
    out = _output_dir()
    return [
        out / "model_registry" / "active_model.json",
        out / "models" / "active_model.json",
        Path("outputs") / "model_registry" / "active_model.json",
        Path("outputs") / "models" / "active_model.json",
    ]


def _customer_prediction_paths() -> list[Path]:
    out = _output_dir()
    return [
        out / "customer_predictions",
        out / "customer_predictions.json",
        Path("outputs") / "customer_predictions",
        Path("outputs") / "customer_predictions.json",
    ]


def _existing(paths: Sequence[Path]) -> list[str]:
    return [str(path) for path in paths if path.exists()]


def _observability_path() -> Path:
    return _output_dir() / "model_research" / "governance_observability_report.json"


def _access_control_path() -> Path:
    return _output_dir() / "model_research" / "governance_access_control_report.json"


def _registry_safety_path() -> Path:
    return _output_dir() / "model_research" / "model_registry_safety_report.json"


def _data_quality_path() -> Path:
    return _output_dir() / "diagnostics" / "managed_data_quality_scorecard.json"


def _freshness_path() -> Path:
    return _output_dir() / "model_research" / "evidence_freshness_report.json"


def _rollback_rehearsal_path() -> Path:
    return _output_dir() / "model_research" / "rollback_rehearsal_report.json"


def _real_lockdown_scenarios() -> list[dict[str, Any]]:
    scenarios: list[dict[str, Any]] = []
    observability = _read_json(_observability_path())
    telemetry = observability.get("telemetry_summary") if isinstance(observability.get("telemetry_summary"), Mapping) else {}
    if str(telemetry.get("secret_scan_status") or "").lower() == "fail":
        scenarios.append(simulate_secret_leak_detection())
    if int(telemetry.get("active_model_violation_count") or 0) > 0 or _existing(_active_model_paths()):
        scenarios.append(simulate_unapproved_active_model())
    if int(telemetry.get("customer_prediction_violation_count") or 0) > 0 or _existing(_customer_prediction_paths()):
        scenarios.append(simulate_unapproved_customer_predictions())
    if int(telemetry.get("forbidden_action_violation_count") or 0) > 0:
        scenarios.append(simulate_forbidden_action_exposure())

    access = _read_json(_access_control_path())
    if int(access.get("ui_api_violations_count") or access.get("forbidden_action_violation_count") or 0) > 0:
        scenarios.append(simulate_forbidden_action_exposure())

    registry = _read_json(_registry_safety_path())
    if bool(registry.get("unapproved_active_detected")):
        scenarios.append(simulate_unapproved_active_model())

    quality = _read_json(_data_quality_path())
    if str(quality.get("status") or "").lower() in {"fail", "failed", "blocked", "violation"}:
        scenarios.append(simulate_data_quality_gate_failed_after_ready())

    freshness = _read_json(_freshness_path())
    if str(freshness.get("status") or "").lower() == "blocked" and bool(freshness.get("approval_attempt_detected")):
        scenarios.append(simulate_stale_evidence_used_for_approval())

    unique: dict[str, dict[str, Any]] = {}
    for scenario in scenarios:
        unique[str(scenario.get("scenario"))] = scenario
    return list(unique.values())


def compute_lockdown_state(scenarios: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    reasons = [
        str(item.get("lockdown_reason") or item.get("scenario") or "")
        for item in scenarios
        if bool(item.get("lockdown_triggered")) and str(item.get("lockdown_reason") or item.get("scenario") or "").strip()
    ]
    lockdown = bool(reasons)
    return _safe_payload(
        {
            "lockdown_triggered": lockdown,
            "lockdown_reasons": list(dict.fromkeys(reasons)),
            "candidate_training_allowed": False,
            "manual_approval_recommended": False,
            "active_publish_allowed": False,
            "customer_prediction_write_allowed": False,
            "next_allowed_action": "resolve_governance_incident" if lockdown else "continue_governance_checks",
            "manual_unlock_required": lockdown,
        }
    )


def _remediation_playbook() -> list[str]:
    return [
        "run rollback rehearsal and review artifact quarantine plan",
        "rotate managed proxy token",
        "disable managed proxy",
        "invalidate cached managed rows",
        "rerun secret scan",
        "rerun setup / health / PIT audit",
        "rebuild evidence bundle",
        "refresh decision board",
        "require manual review before unlocking",
    ]


def _required_human_actions(lockdown_state: Mapping[str, Any]) -> list[str]:
    if not bool(lockdown_state.get("lockdown_triggered")):
        return ["review drill report", "keep break-glass procedure current"]
    return [
        "confirm incident scope",
        "complete remediation playbook",
        "rerun safe governance checks",
        "document manual unlock review",
    ]


def build_incident_drill_report(*, simulation_only: bool = True, write: bool = True) -> dict[str, Any]:
    scenario_results = _simulation_scenarios() if simulation_only else _real_lockdown_scenarios()
    simulated_state = compute_lockdown_state(_simulation_scenarios())
    real_state = compute_lockdown_state(_real_lockdown_scenarios())
    report_state = simulated_state if simulation_only else real_state
    failed = [item for item in scenario_results if not bool(item.get("lockdown_triggered"))]
    status = "pass" if simulation_only and not failed else ("lockdown" if real_state["lockdown_triggered"] else "ready")
    report = {
        "status": status,
        "generated_at": _now(),
        "drill_version": DRILL_VERSION,
        "scenario_results": scenario_results,
        "scenarios_run": len(scenario_results),
        "scenarios_passed": len(scenario_results) - len(failed),
        "scenarios_failed": len(failed),
        "lockdown_triggered": bool(report_state.get("lockdown_triggered")),
        "lockdown_reasons": list(report_state.get("lockdown_reasons") or []),
        "real_lockdown_state": real_state,
        "simulated_lockdown_state": simulated_state,
        "simulated_artifacts_only": True,
        "rollback_rehearsal_available": _rollback_rehearsal_path().exists(),
        "rollback_rehearsal_path": str(_rollback_rehearsal_path()),
        "remediation_playbook": _remediation_playbook(),
        "required_human_actions": _required_human_actions(report_state),
        "decision_board_override": {
            "current_research_state": "governance_lockdown" if real_state["lockdown_triggered"] else "unchanged",
            "next_allowed_action": "resolve_governance_incident" if real_state["lockdown_triggered"] else "continue_governance_checks",
            "candidate_training_allowed": False,
            "manual_approval_recommended": False,
            "active_publish_allowed": False,
            "customer_prediction_write_allowed": False,
        },
        "active_publish_allowed": False,
        "customer_prediction_write_allowed": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    safe = _safe_payload(report)
    if write:
        _report_path().write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def run_incident_drill_simulation(*, simulation_only: bool = True) -> dict[str, Any]:
    run = start_research_run(
        service_name="incident_drill",
        run_type="safe_dry_run",
        output_paths=[str(_report_path())],
    )
    error = ""
    try:
        report = build_incident_drill_report(simulation_only=simulation_only, write=True)
    except Exception as exc:  # pragma: no cover - defensive ledger recording
        error = sanitize_text(str(exc))
        report = {
            "status": "blocked",
            "generated_at": _now(),
            "drill_version": DRILL_VERSION,
            "blocking_reasons": ["incident_drill_failed"],
            "error_summary": error,
            "simulated_artifacts_only": True,
            "active_publish_allowed": False,
            "customer_prediction_write_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": str(_report_path()),
        }
        _report_path().write_text(json.dumps(_safe_payload(report), ensure_ascii=False, indent=2), encoding="utf-8")
    finalized = finalize_research_run(run, error_summary=error)
    append_run_ledger(finalized)
    return _safe_payload(report)


def refresh_lockdown_state_report() -> dict[str, Any]:
    run = start_research_run(
        service_name="governance_lockdown_state",
        run_type="safe_refresh",
        output_paths=[str(_report_path())],
    )
    error = ""
    try:
        report = build_incident_drill_report(simulation_only=False, write=True)
    except Exception as exc:  # pragma: no cover - defensive ledger recording
        error = sanitize_text(str(exc))
        report = {
            "status": "blocked",
            "generated_at": _now(),
            "drill_version": DRILL_VERSION,
            "blocking_reasons": ["lockdown_state_refresh_failed"],
            "error_summary": error,
            "simulated_artifacts_only": True,
            "active_publish_allowed": False,
            "customer_prediction_write_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": str(_report_path()),
        }
        _report_path().write_text(json.dumps(_safe_payload(report), ensure_ascii=False, indent=2), encoding="utf-8")
    finalized = finalize_research_run(run, error_summary=error)
    append_run_ledger(finalized)
    return _safe_payload(report)


def get_incident_drill_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if payload:
        return _safe_payload(payload)
    return build_incident_drill_report(simulation_only=False, write=False)
