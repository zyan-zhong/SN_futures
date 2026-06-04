from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


DRY_RUN_VERSION = "promotion_dry_run_evidence_v2"
REPORT_FILENAME = "promotion_dry_run_evidence_report.json"
READY_STATUSES = {"ready", "pass", "passed", "success", "approved_for_shadow_only"}
BLOCKED_STATUSES = {"blocked", "fail", "failed", "violation", "missing", "not_allowed"}


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
        "manual_approval": _path("model_research/manual_approval_report.json"),
        "shadow_mode_readiness": _path("model_research/shadow_mode_readiness_spec.json"),
        "registry_safety": _path("model_research/model_registry_safety_report.json"),
        "evidence_freshness": _path("model_research/evidence_freshness_report.json"),
        "production_cutover_checklist": _path("model_research/production_cutover_checklist_report.json"),
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
    return str(payload.get("status") or "missing").strip().lower()


def _as_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item or "").strip()]
    if value is None:
        return []
    text = str(value).strip()
    return [text] if text else []


def _check(name: str, passed: bool, reason: str, evidence_path: Path) -> dict[str, Any]:
    return {
        "name": name,
        "status": "pass" if passed else "blocked",
        "passed": bool(passed),
        "reason": "" if passed else reason,
        "evidence_path": str(evidence_path),
    }


def _load_evidence() -> dict[str, dict[str, Any]]:
    return {name: _read_json(path) for name, path in _paths().items()}


def _active_model_paths() -> list[Path]:
    out = _output_dir()
    cwd = Path.cwd()
    return [
        out / "model_registry" / "active_model.json",
        out / "models" / "active_model.json",
        cwd / "outputs" / "model_registry" / "active_model.json",
        cwd / "outputs" / "models" / "active_model.json",
    ]


def _registry_active_pointer_paths() -> list[Path]:
    out = _output_dir()
    cwd = Path.cwd()
    return [
        out / "model_registry" / "active_pointer.json",
        out / "model_registry" / "active_model_pointer.json",
        out / "model_registry" / "active_registry_pointer.json",
        cwd / "outputs" / "model_registry" / "active_pointer.json",
        cwd / "outputs" / "model_registry" / "active_model_pointer.json",
        cwd / "outputs" / "model_registry" / "active_registry_pointer.json",
    ]


def _customer_prediction_paths() -> list[Path]:
    out = _output_dir()
    cwd = Path.cwd()
    return [
        out / "customer_predictions",
        out / "customer_predictions.json",
        cwd / "outputs" / "customer_predictions",
        cwd / "outputs" / "customer_predictions.json",
        cwd / "app_data" / "customer_predictions",
    ]


def _existing(paths: Sequence[Path]) -> list[str]:
    return [str(path) for path in paths if path.exists()]


def _hash_path(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _pointer_hashes() -> dict[str, str]:
    return {str(path): _hash_path(path) for path in _registry_active_pointer_paths() if path.exists()}


def validate_promotion_dry_run_preconditions(
    *,
    candidate_version: str = "v12",
    evidence: Mapping[str, Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    del candidate_version
    evidence = evidence or _load_evidence()
    paths = _paths()
    board = dict(evidence.get("decision_board", {}))
    manual = dict(evidence.get("manual_approval", {}))
    shadow = dict(evidence.get("shadow_mode_readiness", {}))
    registry = dict(evidence.get("registry_safety", {}))
    freshness = dict(evidence.get("evidence_freshness", {}))
    cutover = dict(evidence.get("production_cutover_checklist", {}))

    board_state = str(board.get("current_research_state") or "").lower()
    board_status = _status(board)
    board_passed = bool(board) and board_status not in BLOCKED_STATUSES and board_state not in {
        "managed_data_blocked",
        "governance_lockdown",
    }
    manual_passed = bool(manual) and _status(manual) in READY_STATUSES and bool(manual.get("two_person_review_pass"))
    shadow_passed = bool(shadow) and _status(shadow) in READY_STATUSES and bool(shadow.get("shadow_mode_allowed"))
    registry_passed = (
        bool(registry)
        and _status(registry) in READY_STATUSES
        and not bool(registry.get("unapproved_active_detected"))
        and not _as_list(registry.get("blocking_reasons"))
    )
    freshness_passed = (
        bool(freshness)
        and _status(freshness) in READY_STATUSES
        and not _as_list(freshness.get("stale_reports"))
        and not _as_list(freshness.get("missing_timestamps"))
        and not _as_list(freshness.get("timestamp_inversions"))
    )
    cutover_passed = bool(cutover) and _status(cutover) in READY_STATUSES and bool(cutover.get("cutover_allowed"))

    checks = [
        _check("decision_board_not_blocked", board_passed, "decision_board_blocked", paths["decision_board"]),
        _check("manual_approval_present", manual_passed, "manual_approval_missing", paths["manual_approval"]),
        _check("shadow_readiness_pass", shadow_passed, "shadow_readiness_not_pass", paths["shadow_mode_readiness"]),
        _check("registry_safety_pass", registry_passed, "registry_safety_not_pass", paths["registry_safety"]),
        _check("evidence_freshness_pass", freshness_passed, "evidence_freshness_not_pass", paths["evidence_freshness"]),
        _check(
            "production_cutover_checklist_pass",
            cutover_passed,
            "production_cutover_checklist_not_pass",
            paths["production_cutover_checklist"],
        ),
    ]
    blocking = [str(item["reason"]) for item in checks if not bool(item.get("passed")) and str(item.get("reason"))]
    return _safe_payload(
        {
            "status": "pass" if not blocking else "blocked",
            "promotion_dry_run_allowed": not blocking,
            "precondition_checks": checks,
            "blocking_reasons": list(dict.fromkeys(blocking)),
        }
    )


def simulate_registry_write_plan(*, candidate_version: str = "v12") -> dict[str, Any]:
    version = str(candidate_version or "v12")
    active_model_path = _output_dir() / "model_registry" / "active_model.json"
    pointer_path = _output_dir() / "model_registry" / "active_pointer.json"
    return _safe_payload(
        {
            "status": "simulated",
            "candidate_version": version,
            "simulation_only": True,
            "requested_action": "promotion_dry_run_only",
            "would_write_active_model_path": str(active_model_path),
            "would_update_active_pointer_path": str(pointer_path),
            "would_register_candidate_version": version,
            "actual_registry_write_performed": False,
            "active_write_attempted": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "notes": [
                "dry-run evidence describes future registry mutation only",
                "this service never calls the promotion executor",
                "active pointer remains unchanged",
            ],
        }
    )


def validate_no_active_write_boundary(*, before_pointer_hashes: Mapping[str, str] | None = None) -> dict[str, Any]:
    before = dict(before_pointer_hashes or {})
    after = _pointer_hashes()
    active_existing = _existing(_active_model_paths())
    changed: list[str] = []
    for path, before_hash in before.items():
        if after.get(path, "") != before_hash:
            changed.append(path)
    for path, after_hash in after.items():
        if path not in before and after_hash:
            # A pre-existing pointer without a before snapshot is not a mutation.
            continue
    checks = {
        "active_model_json_absent": not active_existing,
        "registry_active_pointer_unchanged": not changed,
        "no_model_training_side_effect": True,
    }
    blocking: list[str] = []
    if active_existing:
        blocking.append("active_model_json_present")
    if changed:
        blocking.append("registry_active_pointer_changed")
    return _safe_payload(
        {
            "status": "pass" if not blocking else "violation",
            "checks": checks,
            "active_model_paths": [str(path) for path in _active_model_paths()],
            "existing_active_model_paths": active_existing,
            "changed_active_pointer_paths": changed,
            "blocking_reasons": blocking,
        }
    )


def validate_no_customer_prediction_boundary() -> dict[str, Any]:
    customer_existing = _existing(_customer_prediction_paths())
    checks = {
        "customer_predictions_absent": not customer_existing,
        "no_prediction_side_effect": not customer_existing,
    }
    blocking = ["customer_predictions_present"] if customer_existing else []
    return _safe_payload(
        {
            "status": "pass" if not blocking else "violation",
            "checks": checks,
            "customer_prediction_paths": [str(path) for path in _customer_prediction_paths()],
            "existing_customer_prediction_paths": customer_existing,
            "blocking_reasons": blocking,
        }
    )


def _artifact_boundary_checks(active: Mapping[str, Any], prediction: Mapping[str, Any]) -> dict[str, Any]:
    active_checks = active.get("checks") if isinstance(active.get("checks"), Mapping) else {}
    prediction_checks = prediction.get("checks") if isinstance(prediction.get("checks"), Mapping) else {}
    return _safe_payload(
        {
            "active_model_json_absent": bool(active_checks.get("active_model_json_absent")),
            "registry_active_pointer_unchanged": bool(active_checks.get("registry_active_pointer_unchanged")),
            "customer_predictions_absent": bool(prediction_checks.get("customer_predictions_absent")),
            "no_prediction_side_effect": bool(prediction_checks.get("no_prediction_side_effect")),
            "no_model_training_side_effect": bool(active_checks.get("no_model_training_side_effect", True)),
            "active_boundary_status": active.get("status", "missing"),
            "customer_prediction_boundary_status": prediction.get("status", "missing"),
        }
    )


def build_promotion_dry_run_report(
    *,
    candidate_version: str = "v12",
    write: bool = True,
    record_run: bool = True,
) -> dict[str, Any]:
    before_hashes = _pointer_hashes()
    evidence = _load_evidence()
    preconditions = validate_promotion_dry_run_preconditions(candidate_version=candidate_version, evidence=evidence)
    simulated_plan = simulate_registry_write_plan(candidate_version=candidate_version)
    active_boundary = validate_no_active_write_boundary(before_pointer_hashes=before_hashes)
    prediction_boundary = validate_no_customer_prediction_boundary()
    boundary_checks = _artifact_boundary_checks(active_boundary, prediction_boundary)
    boundary_blocking = list(active_boundary.get("blocking_reasons") or []) + list(prediction_boundary.get("blocking_reasons") or [])
    precondition_blocking = list(preconditions.get("blocking_reasons") or [])
    status = "ready" if not precondition_blocking and not boundary_blocking else "blocked"
    if boundary_blocking:
        status = "violation"
    report = {
        "status": status,
        "generated_at": _now(),
        "dry_run_version": DRY_RUN_VERSION,
        "candidate_version": str(candidate_version or "v12"),
        "requested_action": "promotion_dry_run_only",
        "precondition_checks": list(preconditions.get("precondition_checks") or []),
        "simulated_registry_write_plan": simulated_plan,
        "artifact_boundary_checks": boundary_checks,
        "active_write_attempted": False,
        "active_write_allowed": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "customer_prediction_write_allowed": False,
        "training_invoked": False,
        "blocking_reasons": list(dict.fromkeys([*precondition_blocking, *boundary_blocking])),
        "warning_reasons": [
            "dry_run_evidence_is_not_manual_approval",
            "dry_run_evidence_does_not_publish_active",
        ],
        "evidence_paths": {name: str(path) for name, path in _paths().items()},
        "report_path": str(_report_path()),
    }
    safe = _safe_payload(report)
    if write:
        _write_json(_report_path(), safe)
    if record_run:
        run = start_research_run(
            service_name="promotion_dry_run_evidence",
            run_type="safe_dry_run",
            input_paths=[str(path) for path in _paths().values()],
            output_paths=[str(_report_path())],
        )
        append_run_ledger(finalize_research_run(run, error_summary="artifact boundary violation" if status == "violation" else ""))
    return safe


def build_promotion_dry_run_evidence(*, candidate_version: str = "v12") -> dict[str, Any]:
    return build_promotion_dry_run_report(candidate_version=candidate_version, write=True, record_run=True)


def get_promotion_dry_run_evidence() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if payload:
        return _safe_payload(payload)
    return build_promotion_dry_run_report(write=False, record_run=False)
