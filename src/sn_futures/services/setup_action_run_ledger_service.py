from __future__ import annotations

import json
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text


LEDGER_VERSION = "setup_action_run_ledger_v1"
FORBIDDEN_SIDE_EFFECTS = (
    "training",
    "feature_store_v12_build",
    "training_dataset_v12_build",
    "candidate",
    "promotion",
    "active",
    "prediction",
    "customer_prediction",
)
ACTION_LABELS = {
    "refresh_provider_credentials": "Refresh Local API Provider Credentials",
    "refresh_config_handoff": "Refresh Secure Config Handoff",
    "refresh_operator_runbook": "Refresh Operator Runbook",
    "refresh_managed_proxy_setup": "Refresh Managed Proxy Setup",
    "run_provider_smoke": "Run Provider Smoke Test",
    "run_endpoint_smoke": "Run Endpoint Smoke Test",
    "run_sample_fixture_contract": "Run Sample Fixture Contract",
    "refresh_schema_mapping": "Refresh Schema Mapping",
    "run_pit_replay": "Run PIT Replay",
    "run_pit_audit": "Run PIT Audit",
    "refresh_data_quality": "Refresh Data Quality",
    "refresh_decision_board": "Refresh Decision Board",
}
ACTION_ENDPOINTS = {
    "refresh_provider_credentials": "/api/terminal/local-api-provider/refresh-credentials",
    "refresh_config_handoff": "/api/terminal/managed-proxy/refresh-config-handoff",
    "refresh_operator_runbook": "/api/terminal/managed-proxy/refresh-operator-runbook",
    "refresh_managed_proxy_setup": "/api/terminal/managed-proxy/refresh-setup",
    "run_provider_smoke": "/api/terminal/local-api-provider/run-smoke",
    "run_endpoint_smoke": "/api/terminal/managed-proxy/run-endpoint-smoke",
    "run_sample_fixture_contract": "/api/terminal/managed-proxy/run-sample-fixture-contract-tests",
    "refresh_schema_mapping": "/api/terminal/managed-proxy/refresh-schema-mapping",
    "run_pit_replay": "/api/terminal/managed-proxy/run-pit-replay",
    "run_pit_audit": "/api/terminal/managed-proxy/run-audit",
    "refresh_data_quality": "/api/terminal/managed-proxy/refresh-data-quality",
    "refresh_decision_board": "/api/terminal/research/refresh-decision-board",
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _ledger_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / "setup_action_run_ledger.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _telemetry_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / "setup_action_telemetry.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _as_reasons(value: Any) -> list[str]:
    if isinstance(value, list):
        return [sanitize_text(item) for item in value if str(item or "").strip()]
    text = sanitize_text(value)
    return [text] if text else []


def _read_entries() -> list[dict[str, Any]]:
    path = _ledger_path()
    if not path.exists():
        return []
    entries: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            payload = json.loads(line)
        except Exception:
            continue
        if isinstance(payload, Mapping):
            entries.append(dict(payload))
    return entries


def _append_entry(entry: Mapping[str, Any]) -> dict[str, Any]:
    safe = _safe(dict(entry))
    with _ledger_path().open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(safe, ensure_ascii=False, sort_keys=True))
        handle.write("\n")
    return safe


def start_setup_action_run(action_id: str, *, triggered_endpoint: str | None = None) -> dict[str, Any]:
    action = str(action_id or "").strip()
    started = time.perf_counter()
    payload = {
        "run_id": f"setup-action-{uuid.uuid4().hex[:16]}",
        "action_id": action,
        "action_label": ACTION_LABELS.get(action, action.replace("_", " ")),
        "started_at": _now(),
        "finished_at": "",
        "duration_ms": 0,
        "status": "running",
        "blocking_reasons": [],
        "next_allowed_action": "",
        "triggered_endpoint": triggered_endpoint or ACTION_ENDPOINTS.get(action, "/api/terminal/setup-checklist/run-safe-action"),
        "run_type": "safe_setup_action",
        "action_scope": "setup_checklist",
        "forbidden_side_effects": list(FORBIDDEN_SIDE_EFFECTS),
        "input_redacted": True,
        "output_redacted": True,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "_started_monotonic": started,
    }
    return _safe(payload)


def finalize_setup_action_run(
    run_manifest: Mapping[str, Any],
    *,
    status: str,
    blocking_reasons: Sequence[Any] | None = None,
    next_allowed_action: str = "",
) -> dict[str, Any]:
    started = run_manifest.get("_started_monotonic")
    try:
        duration_ms = int((time.perf_counter() - float(started)) * 1000)
    except Exception:
        duration_ms = 0
    payload = dict(run_manifest)
    payload.pop("_started_monotonic", None)
    payload.update(
        {
            "finished_at": _now(),
            "duration_ms": max(duration_ms, 0),
            "status": str(status or "failed"),
            "blocking_reasons": _as_reasons(list(blocking_reasons or [])),
            "next_allowed_action": sanitize_text(next_allowed_action),
            "input_redacted": True,
            "output_redacted": True,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )
    return _safe(payload)


def record_setup_action_result(
    action_id: str,
    *,
    status: str,
    blocking_reasons: Sequence[Any] | None = None,
    next_allowed_action: str = "",
    triggered_endpoint: str | None = None,
) -> dict[str, Any]:
    run = start_setup_action_run(action_id, triggered_endpoint=triggered_endpoint)
    entry = finalize_setup_action_run(run, status=status, blocking_reasons=blocking_reasons, next_allowed_action=next_allowed_action)
    return _append_entry(entry)


def _counts(entries: Sequence[Mapping[str, Any]]) -> dict[str, int]:
    return {
        "successful_action_count": sum(1 for entry in entries if str(entry.get("status")) == "success"),
        "failed_action_count": sum(1 for entry in entries if str(entry.get("status")) == "failed"),
        "blocked_action_count": sum(1 for entry in entries if str(entry.get("status")) == "blocked"),
    }


def _derive_current_step(next_allowed_action: str) -> str:
    action = str(next_allowed_action or "").strip()
    if action in {"configure_local_api_provider_credentials", "configure_local_api_provider", "configure_provider_credentials"}:
        return "configure_local_api_provider_credentials"
    if action in {"enable_managed_proxy", "configure_managed_proxy_endpoint_or_token"}:
        return "configure_local_api_provider_credentials"
    if action.startswith("run_") or action.startswith("refresh_"):
        return action
    return "configure_local_api_provider_credentials"


def get_setup_action_history(limit: int = 20) -> dict[str, Any]:
    entries = list(reversed(_read_entries()))[: max(int(limit or 20), 0)]
    counts = _counts(entries)
    return _safe(
        {
            "status": "ready",
            "generated_at": _now(),
            "ledger_version": LEDGER_VERSION,
            "action_history": entries,
            "history_count": len(entries),
            "ledger_path": str(_ledger_path()),
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            **counts,
        }
    )


def summarize_setup_action_telemetry() -> dict[str, Any]:
    history = get_setup_action_history(limit=100)
    entries = history["action_history"]
    latest = entries[0] if entries else {}
    latest_failures = [entry for entry in entries if str(entry.get("status")) in {"failed", "blocked"}]
    latest_failure = latest_failures[0] if latest_failures else {}
    successes = [entry for entry in entries if str(entry.get("status")) == "success"]
    recommended_next_action = str(latest.get("next_allowed_action") or "configure_local_api_provider_credentials")
    telemetry = {
        "status": "ready",
        "ledger_status": str(history.get("status") or "missing"),
        "generated_at": _now(),
        "telemetry_version": "setup_action_telemetry_v1",
        "latest_action": str(latest.get("action_id") or ""),
        "latest_action_status": str(latest.get("status") or "not_run"),
        "latest_failure_reason": _as_reasons(latest_failure.get("blocking_reasons") or [])[:1],
        "history_count": int(history.get("history_count") or 0),
        "successful_action_count": history["successful_action_count"],
        "failed_action_count": history["failed_action_count"],
        "blocked_action_count": history["blocked_action_count"],
        "last_successful_step": str(successes[0].get("action_id") or "") if successes else "",
        "current_step": _derive_current_step(recommended_next_action),
        "recommended_next_action": recommended_next_action,
        "feature_store_v12_allowed": False,
        "is_prediction_failure": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "telemetry_path": str(_telemetry_path()),
    }
    safe = _safe(telemetry)
    _telemetry_path().write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def attach_setup_action_history_to_checklist_status(checklist_status: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(checklist_status)
    telemetry = summarize_setup_action_telemetry()
    telemetry["current_step"] = str(payload.get("current_step") or "")
    if payload.get("next_allowed_action"):
        telemetry["recommended_next_action"] = str(payload.get("next_allowed_action"))
    history = get_setup_action_history(limit=8)
    payload["setup_action_telemetry"] = telemetry
    payload["setup_action_history"] = history["action_history"]
    payload["setup_action_history_count"] = history["history_count"]
    payload["training_invoked"] = False
    payload["active_updated"] = False
    payload["customer_prediction_generated"] = False
    return _safe(payload)
