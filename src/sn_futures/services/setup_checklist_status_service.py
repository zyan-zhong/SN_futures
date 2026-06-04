from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Mapping

from ..api.json_utils import sanitize_for_json
from ..utils.secret_sanitizer import sanitize_mapping
from .feature_store_v12_input_contract_service import get_latest_v12_input_contract_report
from .managed_data_audit_service import build_managed_audit_manifest, get_latest_managed_audit_manifest
from .managed_data_quality_service import build_managed_data_quality_scorecard, get_latest_managed_data_quality_scorecard
from .managed_pit_replay_service import get_latest_pit_replay_report, run_pit_replay_harness
from .managed_proxy_endpoint_smoke_service import get_latest_endpoint_smoke_report, run_endpoint_smoke_test
from .managed_proxy_config_handoff_service import get_config_handoff_report, refresh_config_handoff_report
from .local_api_provider_hub_service import get_local_api_provider_hub
from .managed_proxy_operator_runbook_service import get_operator_onboarding_runbook, refresh_operator_onboarding_runbook
from .managed_proxy_sample_fixture_service import get_latest_sample_fixture_report, run_fixture_contract_tests
from .managed_proxy_schema_mapper_service import get_schema_mapping_report, refresh_schema_mapping_report
from .managed_proxy_setup_service import get_managed_proxy_setup_status, refresh_managed_proxy_setup
from .prediction_workspace_status_service import build_prediction_workspace_status
from .provider_credentials_service import get_provider_credentials_report, refresh_provider_credentials_report
from .provider_smoke_test_service import get_latest_provider_smoke_report, run_provider_smoke_test
from .research_decision_board_service import build_research_decision_board
from .setup_action_run_ledger_service import (
    attach_setup_action_history_to_checklist_status,
    finalize_setup_action_run,
    record_setup_action_result,
    start_setup_action_run,
)


CHECKLIST_VERSION = "setup_checklist_status_v1"

SAFE_SETUP_ACTIONS = (
    "refresh_provider_credentials",
    "refresh_config_handoff",
    "refresh_operator_runbook",
    "refresh_managed_proxy_setup",
    "run_provider_smoke",
    "run_sample_fixture_contract",
    "refresh_schema_mapping",
    "run_pit_replay",
    "run_pit_audit",
    "refresh_data_quality",
    "refresh_decision_board",
)

FORBIDDEN_SETUP_ACTIONS = (
    "build_feature_store_v12",
    "run_v12_controlled_build",
    "build_training_dataset_v12",
    "train_candidate",
    "run_candidate_v12",
    "promote_model",
    "write_active_model",
    "generate_customer_prediction",
    "write_token",
    "custom_output_path",
)

STEP_ORDER = (
    "configure_local_api_provider_credentials",
    "verify_operator_runbook",
    "run_setup_verification",
    "run_provider_smoke",
    "run_sample_fixture_contract",
    "refresh_schema_mapping",
    "run_pit_replay",
    "run_pit_audit",
    "refresh_data_quality",
    "review_v12_input_contract",
)

STEP_LABELS = {
    "configure_local_api_provider_credentials": "Configure Local API Provider credentials",
    "verify_operator_runbook": "Review Operator Runbook",
    "run_setup_verification": "Run Setup Verification",
    "run_provider_smoke": "Run Provider Smoke Test",
    "run_sample_fixture_contract": "Run Sample Fixture Contract",
    "refresh_schema_mapping": "Refresh Schema Mapping",
    "run_pit_replay": "Run PIT Replay",
    "run_pit_audit": "Run PIT Audit",
    "refresh_data_quality": "Refresh Data Quality",
    "review_v12_input_contract": "Review v12 Input Contract",
}

STEP_ACTIONS = {
    "configure_local_api_provider_credentials": "refresh_provider_credentials",
    "verify_operator_runbook": "refresh_operator_runbook",
    "run_setup_verification": "refresh_managed_proxy_setup",
    "run_provider_smoke": "run_provider_smoke",
    "run_sample_fixture_contract": "run_sample_fixture_contract",
    "refresh_schema_mapping": "refresh_schema_mapping",
    "run_pit_replay": "run_pit_replay",
    "run_pit_audit": "run_pit_audit",
    "refresh_data_quality": "refresh_data_quality",
    "review_v12_input_contract": "refresh_decision_board",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _as_mapping(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def _status(value: Mapping[str, Any], default: str = "missing") -> str:
    text = str(value.get("status") or default).strip().lower()
    return text or default


def _reasons(value: Mapping[str, Any]) -> list[str]:
    raw = value.get("blocking_reasons") or []
    if not isinstance(raw, list):
        return []
    return [str(item) for item in raw if str(item or "").strip()]


def _is_passish(value: Mapping[str, Any]) -> bool:
    return _status(value) in {"pass", "ready", "success", "configured", "complete", "accepted"}


def _is_provider_configured(provider_credentials: Mapping[str, Any]) -> bool:
    return bool(
        provider_credentials.get("provider_credentials_status") == "configured"
        or provider_credentials.get("status") == "configured"
        or provider_credentials.get("configured_providers")
    )


def _disabled_reason(step_id: str, setup_configured: bool) -> str:
    if step_id == "run_provider_smoke" and not setup_configured:
        return "Local API provider credentials are not configured."
    if step_id in {"run_pit_replay", "run_pit_audit", "refresh_data_quality"} and not setup_configured:
        return "Real local API provider data is not available yet."
    if step_id == "review_v12_input_contract":
        return "Upstream provider data, PIT, quality, and local cache gates are not complete."
    return ""


def _step(
    step_id: str,
    *,
    status: str,
    reason: str,
    current_step: str,
    evidence_path: str = "",
    setup_configured: bool = False,
) -> dict[str, Any]:
    action_id = STEP_ACTIONS[step_id]
    action_enabled = action_id in SAFE_SETUP_ACTIONS and status in {"available", "complete"} and not _disabled_reason(step_id, setup_configured)
    disabled_reason = "" if action_enabled else _disabled_reason(step_id, setup_configured)
    if not disabled_reason and not action_enabled and status == "locked":
        disabled_reason = "This step is locked by upstream setup evidence."
    return {
        "step_id": step_id,
        "label": STEP_LABELS[step_id],
        "status": status,
        "short_reason": reason,
        "safe_action_id": action_id,
        "action_enabled": bool(action_enabled),
        "action_disabled_reason": disabled_reason,
        "evidence_path": evidence_path,
        "is_current_step": step_id == current_step,
    }


def derive_setup_step_statuses(
    *,
    provider_credentials: Mapping[str, Any] | None = None,
    provider_smoke: Mapping[str, Any] | None = None,
    setup: Mapping[str, Any] | None = None,
    runbook: Mapping[str, Any] | None = None,
    endpoint_smoke: Mapping[str, Any] | None = None,
    sample_fixture: Mapping[str, Any] | None = None,
    schema_mapping: Mapping[str, Any] | None = None,
    pit_replay: Mapping[str, Any] | None = None,
    pit_audit: Mapping[str, Any] | None = None,
    data_quality: Mapping[str, Any] | None = None,
    v12_input_contract: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    provider_credentials = _as_mapping(provider_credentials)
    provider_smoke = _as_mapping(provider_smoke)
    setup = _as_mapping(setup)
    runbook = _as_mapping(runbook)
    endpoint_smoke = _as_mapping(endpoint_smoke)
    sample_fixture = _as_mapping(sample_fixture)
    schema_mapping = _as_mapping(schema_mapping)
    pit_replay = _as_mapping(pit_replay)
    pit_audit = _as_mapping(pit_audit)
    data_quality = _as_mapping(data_quality)
    v12_input_contract = _as_mapping(v12_input_contract)

    setup_configured = _is_provider_configured(provider_credentials)
    sample_ready = _is_passish(sample_fixture)
    schema_ready = bool(schema_mapping.get("schema_mapping_ready")) or _is_passish(schema_mapping)
    pit_replay_ready = bool(pit_replay.get("point_in_time_join_ready")) or _is_passish(pit_replay)
    pit_audit_ready = bool(pit_audit.get("point_in_time_join_ready")) or _is_passish(pit_audit)
    quality_ready = bool(data_quality.get("gate_passed")) or _is_passish(data_quality)
    input_ready = bool(v12_input_contract.get("input_contract_ready")) and _is_passish(v12_input_contract)

    if not setup_configured:
        current_step = "configure_local_api_provider_credentials"
    elif not _is_passish(provider_smoke):
        current_step = "run_provider_smoke"
    elif not schema_ready:
        current_step = "refresh_schema_mapping"
    elif not pit_replay_ready:
        current_step = "run_pit_replay"
    elif not pit_audit_ready:
        current_step = "run_pit_audit"
    elif not quality_ready:
        current_step = "refresh_data_quality"
    else:
        current_step = "review_v12_input_contract"

    steps = [
        _step(
            "configure_local_api_provider_credentials",
            status="complete" if setup_configured else "available",
            reason="provider credentials configured" if setup_configured else "configure local API provider credentials",
            current_step=current_step,
            evidence_path=str(provider_credentials.get("report_path") or ""),
            setup_configured=setup_configured,
        ),
        _step(
            "verify_operator_runbook",
            status="complete" if _is_passish(runbook) else "available",
            reason="operator runbook can be refreshed safely",
            current_step=current_step,
            evidence_path=str(runbook.get("report_path") or ""),
            setup_configured=setup_configured,
        ),
        _step(
            "run_setup_verification",
            status="complete" if setup_configured else "available",
            reason="legacy proxy setup verification is optional in local API provider mode",
            current_step=current_step,
            evidence_path=str(setup.get("report_path") or ""),
            setup_configured=setup_configured,
        ),
        _step(
            "run_provider_smoke",
            status="complete" if _is_passish(provider_smoke) else "available" if setup_configured else "locked",
            reason="provider smoke requires configured local API provider key",
            current_step=current_step,
            evidence_path=str(provider_smoke.get("report_path") or endpoint_smoke.get("report_path") or ""),
            setup_configured=setup_configured,
        ),
        _step(
            "run_sample_fixture_contract",
            status="complete" if sample_ready else "available",
            reason="sample fixture contract is safe and cannot unlock v12",
            current_step=current_step,
            evidence_path=str(sample_fixture.get("report_path") or ""),
            setup_configured=setup_configured,
        ),
        _step(
            "refresh_schema_mapping",
            status="complete" if schema_ready else "available",
            reason="schema mapping report is safe to refresh",
            current_step=current_step,
            evidence_path=str(schema_mapping.get("report_path") or ""),
            setup_configured=setup_configured,
        ),
        _step(
            "run_pit_replay",
            status="complete" if pit_replay_ready else "available" if setup_configured else "locked",
            reason="PIT replay requires real managed rows",
            current_step=current_step,
            evidence_path=str(pit_replay.get("report_path") or ""),
            setup_configured=setup_configured,
        ),
        _step(
            "run_pit_audit",
            status="complete" if pit_audit_ready else "available" if pit_replay_ready else "locked",
            reason="PIT audit requires PIT replay evidence",
            current_step=current_step,
            evidence_path=str(pit_audit.get("manifest_path") or pit_audit.get("report_path") or ""),
            setup_configured=setup_configured,
        ),
        _step(
            "refresh_data_quality",
            status="complete" if quality_ready else "available" if pit_audit_ready else "locked",
            reason="data quality requires PIT-ready managed rows",
            current_step=current_step,
            evidence_path=str(data_quality.get("report_path") or ""),
            setup_configured=setup_configured,
        ),
        _step(
            "review_v12_input_contract",
            status="complete" if input_ready else "locked",
            reason="v12 input contract is review-only here and never auto-builds v12",
            current_step=current_step,
            evidence_path=str(v12_input_contract.get("report_path") or ""),
            setup_configured=setup_configured,
        ),
    ]
    return steps


def derive_safe_setup_actions(steps: list[Mapping[str, Any]]) -> list[str]:
    return sorted({str(step.get("safe_action_id")) for step in steps if step.get("action_enabled") and str(step.get("safe_action_id")) in SAFE_SETUP_ACTIONS})


def validate_no_forbidden_setup_actions(action_id: str) -> dict[str, Any]:
    action = str(action_id or "").strip()
    if action not in SAFE_SETUP_ACTIONS:
        reason = "forbidden_setup_action" if action in FORBIDDEN_SETUP_ACTIONS else "unknown_setup_action"
        return sanitize_for_json(
            {
                "status": "blocked",
                "action_id": action,
                "blocking_reasons": [reason],
                "allowed_safe_actions": list(SAFE_SETUP_ACTIONS),
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    return sanitize_for_json(
        {
            "status": "allowed",
            "action_id": action,
            "blocking_reasons": [],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def build_setup_checklist_status() -> dict[str, Any]:
    local_provider_hub = get_local_api_provider_hub()
    provider_credentials = get_provider_credentials_report()
    provider_smoke = get_latest_provider_smoke_report()
    handoff = get_config_handoff_report()
    setup = get_managed_proxy_setup_status()
    runbook = get_operator_onboarding_runbook()
    endpoint_smoke = get_latest_endpoint_smoke_report()
    sample_fixture = get_latest_sample_fixture_report()
    schema_mapping = get_schema_mapping_report()
    pit_replay = get_latest_pit_replay_report()
    pit_audit = get_latest_managed_audit_manifest()
    data_quality = get_latest_managed_data_quality_scorecard()
    v12_input_contract = get_latest_v12_input_contract_report()
    prediction = build_prediction_workspace_status()

    steps = derive_setup_step_statuses(
        provider_credentials=provider_credentials,
        provider_smoke=provider_smoke,
        setup=setup,
        runbook=runbook,
        endpoint_smoke=endpoint_smoke,
        sample_fixture=sample_fixture,
        schema_mapping=schema_mapping,
        pit_replay=pit_replay,
        pit_audit=pit_audit,
        data_quality=data_quality,
        v12_input_contract=v12_input_contract,
    )
    current_step = next((str(step["step_id"]) for step in steps if step.get("is_current_step")), STEP_ORDER[0])
    locked_steps = [str(step["step_id"]) for step in steps if step.get("status") == "locked"]
    enabled_actions = derive_safe_setup_actions(steps)
    provider_reasons = _reasons(_as_mapping(provider_credentials))
    prediction_reasons = _reasons(_as_mapping(prediction))
    blocking = list(dict.fromkeys([*provider_reasons, *prediction_reasons]))
    if current_step == "configure_local_api_provider_credentials" and not blocking:
        blocking.append("provider_api_key_missing")

    payload = {
        "status": "ready" if current_step == "review_v12_input_contract" and not blocking else "blocked",
        "generated_at": _now(),
        "checklist_version": CHECKLIST_VERSION,
        "current_step": current_step,
        "provider_mode": "local_api_provider",
        "local_api_provider_hub": local_provider_hub,
        "provider_credentials": provider_credentials,
        "provider_smoke": provider_smoke,
        "config_handoff": handoff,
        "steps": steps,
        "enabled_safe_actions": enabled_actions,
        "locked_steps": locked_steps,
        "safe_actions": list(SAFE_SETUP_ACTIONS),
        "unsafe_actions": list(FORBIDDEN_SETUP_ACTIONS),
        "blocking_reasons": blocking,
        "next_allowed_action": str(
            _as_mapping(local_provider_hub).get("next_allowed_action")
            or _as_mapping(provider_credentials).get("next_allowed_action")
            or _as_mapping(prediction).get("next_allowed_action")
            or "configure_local_api_provider_credentials"
        ),
        "prediction_generation_allowed": bool(_as_mapping(prediction).get("prediction_generation_allowed")),
        "feature_store_v12_allowed": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return attach_setup_action_history_to_checklist_status(sanitize_for_json(payload))


def _safe_action_handlers() -> dict[str, Callable[[], dict[str, Any]]]:
    return {
        "refresh_provider_credentials": refresh_provider_credentials_report,
        "refresh_config_handoff": refresh_config_handoff_report,
        "refresh_operator_runbook": refresh_operator_onboarding_runbook,
        "refresh_managed_proxy_setup": refresh_managed_proxy_setup,
        "run_provider_smoke": run_provider_smoke_test,
        "run_sample_fixture_contract": run_fixture_contract_tests,
        "refresh_schema_mapping": refresh_schema_mapping_report,
        "run_pit_replay": run_pit_replay_harness,
        "run_pit_audit": build_managed_audit_manifest,
        "refresh_data_quality": build_managed_data_quality_scorecard,
        "refresh_decision_board": build_research_decision_board,
    }


def run_setup_checklist_safe_action(action_id: str) -> dict[str, Any]:
    validation = validate_no_forbidden_setup_actions(action_id)
    if validation["status"] != "allowed":
        return validation
    action = str(action_id)
    handler = _safe_action_handlers()[action]
    run_manifest = start_setup_action_run(action)
    try:
        result = handler()
    except Exception as exc:
        checklist_status = build_setup_checklist_status()
        reasons = [str(exc)]
        setup_run = finalize_setup_action_run(
            run_manifest,
            status="failed",
            blocking_reasons=reasons,
            next_allowed_action=str(checklist_status.get("next_allowed_action") or ""),
        )
        record_setup_action_result(
            action,
            status="failed",
            blocking_reasons=reasons,
            next_allowed_action=str(checklist_status.get("next_allowed_action") or ""),
            triggered_endpoint=str(setup_run.get("triggered_endpoint") or ""),
        )
        return sanitize_for_json(
            {
                "status": "failed",
                "action_id": action,
                "blocking_reasons": reasons,
                "checklist_status": checklist_status,
                "setup_action_run": setup_run,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    checklist_status = build_setup_checklist_status()
    setup_run = finalize_setup_action_run(
        run_manifest,
        status="success",
        blocking_reasons=[],
        next_allowed_action=str(checklist_status.get("next_allowed_action") or ""),
    )
    record_setup_action_result(
        action,
        status="success",
        blocking_reasons=[],
        next_allowed_action=str(checklist_status.get("next_allowed_action") or ""),
        triggered_endpoint=str(setup_run.get("triggered_endpoint") or ""),
    )
    checklist_status = build_setup_checklist_status()
    payload = {
        "status": "success",
        "action_id": action,
        "action_result": sanitize_mapping(_as_mapping(result)),
        "checklist_status": checklist_status,
        "setup_action_run": setup_run,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    if action == "run_sample_fixture_contract":
        payload["feature_store_v12_allowed"] = False
    return sanitize_for_json(payload)
