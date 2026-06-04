from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_text
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


APPROVAL_VERSION = "manual_approval_v1"
ALLOWED_REQUESTED_ACTIONS = {"shadow_mode_only", "promotion_dry_run_only", "registry_review_only"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / "manual_approval_report.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _path(relative: str) -> Path:
    primary = _output_dir() / relative
    if primary.exists():
        return primary
    fallback = Path("outputs") / relative
    if fallback.exists():
        return fallback
    return primary


def _decision_board_path() -> Path:
    return _path("model_research/research_decision_board.json")


def _evidence_bundle_path() -> Path:
    return _path("model_research/evidence_bundle_index.json")


def _registry_safety_path() -> Path:
    return _path("model_research/model_registry_safety_report.json")


def _shadow_readiness_path() -> Path:
    return _path("model_research/shadow_mode_readiness_spec.json")


def _incident_drill_path() -> Path:
    return _path("model_research/incident_drill_report.json")


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


def _write_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = _safe_payload(dict(payload))
    _report_path().write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _status(payload: Mapping[str, Any] | None) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    return str(payload.get("status") or "missing").lower()


def _expired(expires_at: Any) -> bool:
    if not expires_at:
        return False
    try:
        return datetime.fromisoformat(str(expires_at).replace("Z", "+00:00")) < datetime.now()
    except Exception:
        return True


def _precondition(name: str, passed: bool, reason: str = "") -> dict[str, Any]:
    return {"name": name, "status": "pass" if passed else "blocked", "passed": bool(passed), "reason": "" if passed else reason}


def validate_manual_approval_preconditions(
    *,
    decision_board: Mapping[str, Any],
    evidence_bundle: Mapping[str, Any],
    registry_safety: Mapping[str, Any],
    shadow_readiness: Mapping[str, Any],
    incident_drill: Mapping[str, Any],
    requested_action: str,
) -> dict[str, Any]:
    requested = str(requested_action or "").strip() or "shadow_mode_only"
    board_status = _status(decision_board)
    board_blocking = _as_list(decision_board.get("blocking_reasons"))
    stale_reports = _as_list(decision_board.get("stale_or_missing_reports"))
    candidate_v10 = decision_board.get("candidate_v10_summary") if isinstance(decision_board.get("candidate_v10_summary"), Mapping) else {}
    lockdown = incident_drill.get("real_lockdown_state") if isinstance(incident_drill.get("real_lockdown_state"), Mapping) else {}
    bundle_status = _status(evidence_bundle)
    bundle_missing = not evidence_bundle
    bundle_missing_reports = _as_list(evidence_bundle.get("missing_reports"))
    bundle_incomplete_reports = _as_list(evidence_bundle.get("incomplete_reports"))
    shadow_allowed = bool(shadow_readiness.get("shadow_mode_allowed"))

    checks = [
        _precondition("requested_action_allowed", requested in ALLOWED_REQUESTED_ACTIONS, "requested_action_not_allowed"),
        _precondition("decision_board_not_blocked", board_status not in {"blocked", "missing", "fail", "failed"}, "decision_board_blocked"),
        _precondition("manual_approval_recommended", bool(decision_board.get("manual_approval_recommended")), "manual_approval_not_recommended"),
        _precondition(
            "cost_attribution_pass",
            bool(candidate_v10.get("cost_attribution_pass", True)) and not any(str(item).startswith("cost_attribution:") for item in board_blocking),
            "cost_attribution_failed",
        ),
        _precondition("evidence_not_stale", not stale_reports, "stale_evidence_present"),
        _precondition(
            "evidence_bundle_present",
            bool(evidence_bundle) and bundle_status not in {"missing", "blocked", "fail", "failed"} and not bundle_missing_reports and not bundle_incomplete_reports,
            "evidence_bundle_missing" if bundle_missing else "evidence_bundle_incomplete",
        ),
        _precondition("incident_lockdown_clear", not bool(lockdown.get("lockdown_triggered")), "incident_lockdown_active"),
        _precondition(
            "shadow_mode_allowed",
            requested != "shadow_mode_only" or shadow_allowed,
            "shadow_mode_not_allowed",
        ),
        _precondition("registry_safety_present", bool(registry_safety), "registry_safety_missing"),
        _precondition("active_write_remains_disabled", not bool(registry_safety.get("active_write_allowed")), "active_write_must_remain_disabled"),
    ]
    reasons = [str(item["reason"]) for item in checks if not bool(item.get("passed")) and str(item.get("reason"))]
    return _safe_payload(
        {
            "approval_request_allowed": not reasons,
            "precondition_checks": checks,
            "blocking_reasons": list(dict.fromkeys(reasons)),
            "requested_action": requested,
        }
    )


def validate_reviewer_identity_shape(reviewer: Mapping[str, Any]) -> dict[str, Any]:
    raw_reviewer_id = str(reviewer.get("reviewer_id") or reviewer.get("id") or "").strip()
    raw_display_name = str(reviewer.get("display_name") or reviewer.get("name") or "").strip()
    reviewer_id = sanitize_text(raw_reviewer_id)
    display_name = sanitize_text(raw_display_name)
    raw_identity = f"{raw_reviewer_id} {raw_display_name}".lower()
    reasons: list[str] = []
    if not reviewer_id:
        reasons.append("reviewer_id_missing")
    if not display_name:
        reasons.append("reviewer_display_name_missing")
    if (
        "***" in reviewer_id
        or "***" in display_name
        or "authorization:" in raw_identity
        or "bearer " in raw_identity
        or "token=" in raw_identity
    ):
        reasons.append("reviewer_identity_contains_secret_like_value")
    return _safe_payload(
        {
            "valid": not reasons,
            "reviewer": {"reviewer_id": reviewer_id, "display_name": display_name},
            "blocking_reasons": reasons,
        }
    )


def validate_two_person_review(reviewers: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    normalized: list[dict[str, str]] = []
    reasons: list[str] = []
    for reviewer in reviewers:
        identity = validate_reviewer_identity_shape(reviewer)
        if not identity["valid"]:
            reasons.extend(identity["blocking_reasons"])
        normalized.append(dict(identity["reviewer"]))
    reviewer_ids = [item["reviewer_id"] for item in normalized if item.get("reviewer_id")]
    if len(normalized) < 2:
        reasons.append("reviewer_count_below_two")
    if len(set(reviewer_ids)) != len(reviewer_ids):
        reasons.append("reviewers_must_be_distinct")
    return _safe_payload(
        {
            "two_person_review_pass": not reasons,
            "reviewers": normalized,
            "reviewer_count": len(normalized),
            "blocking_reasons": list(dict.fromkeys(reasons)),
        }
    )


def _load_inputs() -> dict[str, Any]:
    return {
        "decision_board": _read_json(_decision_board_path()),
        "evidence_bundle": _read_json(_evidence_bundle_path()),
        "registry_safety": _read_json(_registry_safety_path()),
        "shadow_readiness": _read_json(_shadow_readiness_path()),
        "incident_drill": _read_json(_incident_drill_path()),
        "linked_decision_board_path": str(_decision_board_path()),
        "linked_evidence_bundle_path": str(_evidence_bundle_path()),
        "linked_registry_safety_path": str(_registry_safety_path()),
        "linked_shadow_readiness_path": str(_shadow_readiness_path()),
    }


def _base_report(
    *,
    status: str,
    candidate_version: str,
    requested_action: str,
    preconditions: Mapping[str, Any],
    reviewers: Sequence[Mapping[str, Any]] | None = None,
    approval_decision: str = "none",
    expires_at: str = "",
) -> dict[str, Any]:
    review = validate_two_person_review(reviewers or [])
    inputs = _load_inputs()
    return _safe_payload(
        {
            "status": status,
            "generated_at": _now(),
            "approval_version": APPROVAL_VERSION,
            "candidate_version": str(candidate_version or "v12"),
            "requested_action": str(requested_action or "shadow_mode_only"),
            "approval_request_allowed": bool(preconditions.get("approval_request_allowed")),
            "approval_decision": approval_decision,
            "reviewers": review["reviewers"],
            "reviewer_count": review["reviewer_count"],
            "two_person_review_pass": review["two_person_review_pass"],
            "expires_at": expires_at,
            "linked_decision_board_path": inputs["linked_decision_board_path"],
            "linked_evidence_bundle_path": inputs["linked_evidence_bundle_path"],
            "linked_registry_safety_path": inputs["linked_registry_safety_path"],
            "linked_shadow_readiness_path": inputs["linked_shadow_readiness_path"],
            "precondition_checks": list(preconditions.get("precondition_checks") or []),
            "blocking_reasons": list(preconditions.get("blocking_reasons") or []) + ([] if review["two_person_review_pass"] or not reviewers else list(review["blocking_reasons"])),
            "warning_reasons": ["active_publish_is_not_supported_here"],
            "active_write_allowed": False,
            "customer_prediction_write_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": str(_report_path()),
        }
    )


def build_manual_approval_report(
    *,
    requested_action: str = "shadow_mode_only",
    candidate_version: str = "v12",
    write: bool = True,
) -> dict[str, Any]:
    inputs = _load_inputs()
    preconditions = validate_manual_approval_preconditions(
        decision_board=inputs["decision_board"],
        evidence_bundle=inputs["evidence_bundle"],
        registry_safety=inputs["registry_safety"],
        shadow_readiness=inputs["shadow_readiness"],
        incident_drill=inputs["incident_drill"],
        requested_action=requested_action,
    )
    status = "not_requested" if preconditions["approval_request_allowed"] else "blocked_by_gates"
    report = _base_report(
        status=status,
        candidate_version=candidate_version,
        requested_action=preconditions["requested_action"],
        preconditions=preconditions,
    )
    return _write_report(report) if write else report


def build_manual_approval_status() -> dict[str, Any]:
    existing = _read_json(_report_path())
    if existing:
        if existing.get("status") == "pending_review" and _expired(existing.get("expires_at")):
            existing["status"] = "expired"
            existing["blocking_reasons"] = list(dict.fromkeys([*_as_list(existing.get("blocking_reasons")), "approval_expired"]))
            existing["approval_request_allowed"] = False
            existing["active_write_allowed"] = False
            existing["customer_prediction_write_allowed"] = False
            return _safe_payload(existing)
        return _safe_payload(existing)
    return build_manual_approval_report(write=False)


def create_manual_approval_request(
    *,
    requested_action: str = "shadow_mode_only",
    candidate_version: str = "v12",
    expires_in_hours: int = 72,
) -> dict[str, Any]:
    inputs = _load_inputs()
    preconditions = validate_manual_approval_preconditions(
        decision_board=inputs["decision_board"],
        evidence_bundle=inputs["evidence_bundle"],
        registry_safety=inputs["registry_safety"],
        shadow_readiness=inputs["shadow_readiness"],
        incident_drill=inputs["incident_drill"],
        requested_action=requested_action,
    )
    status = "pending_review" if preconditions["approval_request_allowed"] else "blocked_by_gates"
    expires_at = (datetime.now() + timedelta(hours=max(1, int(expires_in_hours)))).isoformat(timespec="seconds") if status == "pending_review" else ""
    report = _base_report(
        status=status,
        candidate_version=candidate_version,
        requested_action=preconditions["requested_action"],
        preconditions=preconditions,
        expires_at=expires_at,
    )
    _write_report(report)
    _record_ledger("manual_approval_request")
    return report


def record_manual_approval_decision(
    *,
    decision: str,
    reviewers: Sequence[Mapping[str, Any]],
    notes: str = "",
) -> dict[str, Any]:
    existing = build_manual_approval_status()
    requested_action = str(existing.get("requested_action") or "shadow_mode_only")
    preconditions = {
        "approval_request_allowed": bool(existing.get("approval_request_allowed")),
        "precondition_checks": list(existing.get("precondition_checks") or []),
        "blocking_reasons": list(existing.get("blocking_reasons") or []),
        "requested_action": requested_action,
    }
    if existing.get("status") == "expired" or _expired(existing.get("expires_at")):
        report = {**existing, "status": "expired", "approval_request_allowed": False}
        report["blocking_reasons"] = list(dict.fromkeys([*_as_list(report.get("blocking_reasons")), "approval_expired"]))
        report["active_write_allowed"] = False
        report["customer_prediction_write_allowed"] = False
        _write_report(report)
        _record_ledger("manual_approval_decision")
        return _safe_payload(report)
    review = validate_two_person_review(reviewers)
    normalized_decision = str(decision or "").strip().lower()
    if normalized_decision == "reject":
        status = "rejected"
    elif normalized_decision == "approve" and review["two_person_review_pass"] and existing.get("status") == "pending_review":
        status = "approved_for_shadow_only" if requested_action == "shadow_mode_only" else "approved_for_dry_run_promotion_only"
    else:
        status = "pending_review"
    report = _base_report(
        status=status,
        candidate_version=str(existing.get("candidate_version") or "v12"),
        requested_action=requested_action,
        preconditions=preconditions,
        reviewers=review["reviewers"],
        approval_decision=normalized_decision or "none",
        expires_at=str(existing.get("expires_at") or ""),
    )
    if notes:
        report["decision_notes"] = sanitize_text(notes)
    if not review["two_person_review_pass"]:
        report["blocking_reasons"] = list(dict.fromkeys([*_as_list(report.get("blocking_reasons")), *review["blocking_reasons"]]))
    _write_report(report)
    _record_ledger("manual_approval_decision")
    return _safe_payload(report)


def refresh_manual_approval_status() -> dict[str, Any]:
    report = build_manual_approval_report(write=True)
    _record_ledger("manual_approval_status")
    return report


def _record_ledger(service_name: str) -> None:
    run = start_research_run(
        service_name=service_name,
        run_type="governance_report_refresh",
        output_paths=[str(_report_path())],
    )
    finalized = finalize_research_run(run)
    append_run_ledger(finalized)
