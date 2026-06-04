from __future__ import annotations

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


CUTOVER_VERSION = "production_cutover_checklist_v1"
REPORT_FILENAME = "production_cutover_checklist_report.json"
NOOP_PLAN_FILENAME = "noop_release_plan.json"
FORBIDDEN_ACTIONS = (
    "training",
    "oof_generation",
    "feature_store_v12_build",
    "training_dataset_v12_build",
    "candidate_research",
    "promotion",
    "active_model_write",
    "customer_prediction_write",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _noop_plan_path() -> Path:
    path = _output_dir() / "model_research" / NOOP_PLAN_FILENAME
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
        "manual_approval": _path("model_research/manual_approval_report.json"),
        "shadow_mode_readiness": _path("model_research/shadow_mode_readiness_spec.json"),
        "shadow_output_contract": _path("model_research/shadow_output_contract_report.json"),
        "registry_safety": _path("model_research/model_registry_safety_report.json"),
        "incident_drill": _path("model_research/incident_drill_report.json"),
        "observability": _path("model_research/governance_observability_report.json"),
        "evidence_freshness": _path("model_research/evidence_freshness_report.json"),
        "external_audit_export": _path("governance/external_audit_export/audit_index.json"),
        "post_release_monitoring_spec": _path("model_research/post_release_monitoring_spec_report.json"),
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


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None


def _expired(expires_at: Any) -> bool:
    parsed = _parse_dt(expires_at)
    if parsed is None:
        return False
    return parsed < datetime.now()


def _check(name: str, passed: bool, reason: str, evidence_path: str = "") -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "blocked",
        "passed": bool(passed),
        "reason": "" if passed else reason,
        "evidence_path": evidence_path,
    }


def _active_model_paths() -> list[Path]:
    output = _output_dir()
    cwd = Path.cwd()
    return [
        output / "model_registry" / "active_model.json",
        output / "models" / "active_model.json",
        cwd / "outputs" / "model_registry" / "active_model.json",
        cwd / "outputs" / "models" / "active_model.json",
    ]


def _customer_prediction_paths() -> list[Path]:
    output = _output_dir()
    cwd = Path.cwd()
    return [
        output / "customer_predictions",
        output / "customer_predictions.json",
        cwd / "outputs" / "customer_predictions",
        cwd / "outputs" / "customer_predictions.json",
        cwd / "app_data" / "customer_predictions",
    ]


def _existing(paths: Sequence[Path]) -> list[str]:
    return [str(path) for path in paths if path.exists()]


def _load_evidence() -> dict[str, dict[str, Any]]:
    return {name: _read_json(path) for name, path in _paths().items()}


def _rollback_summary(registry_safety: Mapping[str, Any]) -> dict[str, Any]:
    rollback = registry_safety.get("rollback_plan") if isinstance(registry_safety.get("rollback_plan"), Mapping) else {}
    top_level_available = registry_safety.get("rollback_target_available")
    available = bool(top_level_available) if top_level_available is not None else bool(rollback.get("rollback_target_available"))
    return _safe_payload(
        {
            "status": "ready" if available and str(rollback.get("status") or "ready").lower() not in {"blocked", "fail", "failed", "violation"} else "blocked",
            "rollback_target_available": available,
            "selected_rollback_target": rollback.get("selected_rollback_target", {}),
            "blocking_reasons": _as_list(rollback.get("blocking_reasons")) or ([] if available else ["rollback_target_missing"]),
        }
    )


def validate_cutover_preconditions(evidence: Mapping[str, Mapping[str, Any]] | None = None) -> dict[str, Any]:
    evidence = evidence or _load_evidence()
    paths = _paths()
    board = evidence.get("decision_board", {})
    manual = evidence.get("manual_approval", {})
    shadow = evidence.get("shadow_mode_readiness", {})
    shadow_contract = evidence.get("shadow_output_contract", {})
    registry = evidence.get("registry_safety", {})
    incident = evidence.get("incident_drill", {})
    observability = evidence.get("observability", {})
    freshness = evidence.get("evidence_freshness", {})
    audit = evidence.get("external_audit_export", {})
    monitoring = evidence.get("post_release_monitoring_spec", {})
    rollback = _rollback_summary(registry)

    real_lockdown = incident.get("real_lockdown_state") if isinstance(incident.get("real_lockdown_state"), Mapping) else {}
    slo = observability.get("slo_results") if isinstance(observability.get("slo_results"), Mapping) else {}
    checks = [
        _check(
            "decision_board_ready_for_manual_review",
            _status(board) in {"ready", "pass", "success"} and board.get("current_research_state") == "ready_for_manual_review" and bool(board.get("manual_approval_recommended")),
            "decision_board_not_ready_for_manual_review",
            str(paths["decision_board"]),
        ),
        _check(
            "manual_approval_present_and_not_expired",
            bool(manual) and bool(manual.get("two_person_review_pass")) and not _expired(manual.get("expires_at")),
            "manual_approval_missing_or_expired",
            str(paths["manual_approval"]),
        ),
        _check(
            "shadow_mode_readiness_pass",
            _status(shadow) in {"ready", "pass", "success"} and bool(shadow.get("shadow_mode_allowed")),
            "shadow_mode_readiness_not_pass",
            str(paths["shadow_mode_readiness"]),
        ),
        _check(
            "shadow_output_contract_pass",
            _status(shadow_contract) in {"ready", "pass", "success"} and bool(shadow_contract.get("shadow_output_allowed")) and str(shadow_contract.get("path_isolation_status") or "").lower() == "pass" and str(shadow_contract.get("schema_validation_status") or "").lower() == "pass" and str(shadow_contract.get("customer_prediction_collision_status") or "").lower() == "pass",
            "shadow_output_contract_not_pass",
            str(paths["shadow_output_contract"]),
        ),
        _check(
            "registry_safety_pass",
            _status(registry) in {"ready", "pass", "success"} and not bool(registry.get("unapproved_active_detected")),
            "registry_safety_not_pass",
            str(paths["registry_safety"]),
        ),
        _check(
            "incident_drill_pass",
            _status(incident) in {"ready", "pass", "success"} and not bool(real_lockdown.get("lockdown_triggered")) and int(incident.get("scenarios_failed") or 0) == 0,
            "incident_drill_not_pass",
            str(paths["incident_drill"]),
        ),
        _check(
            "observability_slo_pass",
            _status(observability) in {"ready", "pass", "success"} and str(slo.get("status") or observability.get("slo_status") or "pass").lower() in {"ready", "pass", "success"},
            "observability_slo_not_pass",
            str(paths["observability"]),
        ),
        _check(
            "evidence_freshness_pass",
            _status(freshness) in {"ready", "pass", "success"} and not _as_list(freshness.get("stale_reports")) and not _as_list(freshness.get("missing_timestamps")) and not _as_list(freshness.get("timestamp_inversions")),
            "evidence_freshness_not_pass",
            str(paths["evidence_freshness"]),
        ),
        _check(
            "external_audit_export_ready",
            _status(audit) == "ready" and str(audit.get("redaction_status") or "pass").lower() == "pass" and not _as_list(audit.get("missing_reports")) and not _as_list(audit.get("incomplete_reports")),
            "external_audit_export_not_ready",
            str(paths["external_audit_export"]),
        ),
        _check(
            "post_release_monitoring_spec_ready",
            _status(monitoring) in {"ready", "pass", "success"} and bool(monitoring.get("live_monitoring_enabled")),
            "post_release_monitoring_spec_not_ready",
            str(paths["post_release_monitoring_spec"]),
        ),
        _check(
            "rollback_plan_available",
            bool(rollback.get("rollback_target_available")),
            "rollback_target_missing",
            str(paths["registry_safety"]),
        ),
    ]
    blocking = [str(item["reason"]) for item in checks if not bool(item.get("passed")) and str(item.get("reason"))]
    return _safe_payload(
        {
            "status": "pass" if not blocking else "blocked",
            "cutover_allowed": not blocking,
            "precondition_checks": checks,
            "blocking_reasons": sorted(set(blocking)),
        }
    )


def build_noop_release_plan(*, intended_candidate_version: str = "v12", write: bool = True, record_run: bool = True) -> dict[str, Any]:
    plan = {
        "status": "ready",
        "generated_at": _now(),
        "release_plan_id": f"noop-{uuid.uuid4().hex[:12]}",
        "release_type": "noop",
        "intended_candidate_version": str(intended_candidate_version or "v12"),
        "steps": [
            "review cutover checklist",
            "review external audit export",
            "confirm no active publish action will run",
            "confirm no customer prediction output will be generated",
            "record human signoff requirement",
            "stop before any production mutation",
        ],
        "expected_no_side_effects": [
            "no active_model.json write",
            "no customer_predictions write",
            "no promotion execution",
            "no model training",
            "no OOF generation",
        ],
        "forbidden_outputs": [str(path) for path in _active_model_paths() + _customer_prediction_paths()],
        "rollback_drill_required": True,
        "signoff_required": True,
        "noop_release_plan_ready": True,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "plan_path": str(_noop_plan_path()),
    }
    side_effects = validate_noop_release_has_no_side_effects(plan)
    if side_effects["status"] != "pass":
        plan["status"] = "blocked"
        plan["noop_release_plan_ready"] = False
        plan["blocking_reasons"] = side_effects["blocking_reasons"]
    safe = _safe_payload(plan)
    if write:
        _write_json(_noop_plan_path(), safe)
    if record_run:
        run = start_research_run(
            service_name="production_noop_release_plan",
            run_type="safe_dry_run",
            output_paths=[str(_noop_plan_path())],
        )
        append_run_ledger(finalize_research_run(run))
    return safe


def validate_noop_release_has_no_side_effects(plan: Mapping[str, Any] | None = None) -> dict[str, Any]:
    blocking: list[str] = []
    if _existing(_active_model_paths()):
        blocking.append("active_model_output_exists")
    if _existing(_customer_prediction_paths()):
        blocking.append("customer_prediction_output_exists")
    if bool((plan or {}).get("training_invoked")):
        blocking.append("noop_plan_must_not_train")
    if bool((plan or {}).get("active_updated")):
        blocking.append("noop_plan_must_not_write_active")
    if bool((plan or {}).get("customer_prediction_generated")):
        blocking.append("noop_plan_must_not_generate_prediction")
    return _safe_payload({"status": "pass" if not blocking else "blocked", "blocking_reasons": sorted(set(blocking))})


def build_production_cutover_checklist() -> dict[str, Any]:
    evidence = _load_evidence()
    preconditions = validate_cutover_preconditions(evidence)
    noop_plan = build_noop_release_plan(write=False, record_run=False)
    return _safe_payload(
        {
            "status": "ready" if preconditions["cutover_allowed"] else "blocked",
            "generated_at": _now(),
            "cutover_version": CUTOVER_VERSION,
            "cutover_allowed": bool(preconditions["cutover_allowed"]),
            "noop_release_plan_ready": bool(noop_plan.get("noop_release_plan_ready")),
            "precondition_checks": list(preconditions["precondition_checks"]),
            "required_manual_steps": [
                "review all precondition checks",
                "review external audit export with reviewer",
                "confirm rollback target and drill",
                "confirm no active publish or customer prediction action is run by this checklist",
                "obtain separate explicit approval before any production mutation",
            ],
            "rollback_plan_summary": _rollback_summary(evidence.get("registry_safety", {})),
            "observability_requirements": {
                "slo_status_required": "pass",
                "runtime_scan_status_required": "pass",
                "stale_critical_reports_required": 0,
            },
            "incident_response_requirements": [
                "incident drill pass",
                "real lockdown state clear",
                "manual unlock procedure documented",
            ],
            "forbidden_actions": list(FORBIDDEN_ACTIONS),
            "blocking_reasons": list(preconditions["blocking_reasons"]),
            "evidence": evidence,
            "active_publish_allowed": False,
            "customer_prediction_write_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": str(_report_path()),
            "noop_plan_path": str(_noop_plan_path()),
        }
    )


def build_cutover_report(*, write: bool = True, record_run: bool = True) -> dict[str, Any]:
    report = build_production_cutover_checklist()
    if write:
        _write_json(_report_path(), report)
    if record_run:
        run = start_research_run(
            service_name="production_cutover_checklist",
            run_type="report_write",
            output_paths=[str(_report_path())],
        )
        append_run_ledger(finalize_research_run(run))
    return report


def get_production_cutover_checklist() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if payload:
        return _safe_payload(payload)
    return build_cutover_report(write=False, record_run=False)
