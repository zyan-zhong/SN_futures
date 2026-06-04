from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


ROLLBACK_REHEARSAL_VERSION = "rollback_rehearsal_v1"
REPORT_FILENAME = "rollback_rehearsal_report.json"
QUARANTINE_MANIFEST_FILENAME = "rollback_quarantine_manifest.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _quarantine_manifest_path() -> Path:
    path = _output_dir() / "model_research" / QUARANTINE_MANIFEST_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _safe_payload(payload: Any) -> Any:
    if isinstance(payload, Mapping):
        return {
            sanitize_text(str(key)): _safe_payload(value)
            for key, value in sanitize_for_json(sanitize_mapping(payload)).items()
        }
    if isinstance(payload, list):
        return [_safe_payload(item) for item in payload]
    if isinstance(payload, str):
        return sanitize_text(payload)
    return sanitize_for_json(payload)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists() or not path.is_file():
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


def _workspace_outputs_dir() -> Path:
    return Path.cwd() / "outputs"


def _candidate_path(relative_path: str) -> Path:
    primary = _output_dir() / relative_path
    if primary.exists():
        return primary
    fallback = _workspace_outputs_dir() / relative_path
    if fallback.exists():
        return fallback
    return primary


def _linked_paths() -> dict[str, str]:
    return {
        "linked_incident_drill_path": str(_candidate_path("model_research/incident_drill_report.json")),
        "linked_registry_safety_path": str(_candidate_path("model_research/model_registry_safety_report.json")),
        "linked_monitoring_spec_path": str(_candidate_path("model_research/post_release_monitoring_spec_report.json")),
        "linked_decision_board_path": str(_candidate_path("model_research/research_decision_board.json")),
    }


def _active_model_paths() -> list[Path]:
    out = _output_dir()
    cwd = _workspace_outputs_dir()
    return [
        out / "model_registry" / "active_model.json",
        out / "models" / "active_model.json",
        cwd / "model_registry" / "active_model.json",
        cwd / "models" / "active_model.json",
    ]


def _registry_active_pointer_paths() -> list[Path]:
    out = _output_dir()
    cwd = _workspace_outputs_dir()
    names = ("active_pointer.json", "active_model_pointer.json", "registry_active_pointer.json")
    return [root / "model_registry" / name for root in (out, cwd) for name in names]


def _customer_prediction_paths() -> list[Path]:
    out = _output_dir()
    cwd = _workspace_outputs_dir()
    return [
        out / "customer_predictions",
        out / "customer_predictions.json",
        out.parent / "customer_predictions",
        out.parent / "customer_predictions.json",
        cwd / "customer_predictions",
        cwd / "customer_predictions.json",
        Path.cwd() / "app_data" / "customer_predictions",
        Path.cwd() / "app_data" / "customer_predictions.json",
    ]


def _registry_active_dirs() -> list[Path]:
    out = _output_dir()
    cwd = _workspace_outputs_dir()
    return [out / "model_registry" / "active", cwd / "model_registry" / "active"]


def _promotion_artifact_candidates() -> list[Path]:
    out = _output_dir()
    cwd = _workspace_outputs_dir()
    candidates: list[Path] = []
    for root in (out / "model_registry", cwd / "model_registry"):
        if root.exists():
            candidates.extend(root.glob("promotion_report*.json"))
    for root in (out / "model_research", cwd / "model_research"):
        if root.exists():
            candidates.extend(root.glob("candidate_*/promotion*.json"))
    return candidates


def _dedupe_paths(paths: Sequence[Path]) -> list[Path]:
    seen: set[str] = set()
    out: list[Path] = []
    for path in paths:
        key = str(path)
        try:
            key = str(path.resolve())
        except Exception:
            pass
        if key in seen:
            continue
        seen.add(key)
        out.append(path)
    return out


def _artifact(path: Path, artifact_type: str, reason: str, recommended_action: str) -> dict[str, Any]:
    return _safe_payload(
        {
            "original_path": str(path),
            "artifact_type": artifact_type,
            "reason": reason,
            "recommended_action": recommended_action,
        }
    )


def _path_contains_shadow_collision(path: Path) -> bool:
    text = str(path).lower()
    return "customer_predictions" in text and ("shadow" in text or "shadow_mode" in text)


def _scan_shadow_collisions(customer_roots: Sequence[Path]) -> list[Path]:
    collisions: list[Path] = []
    for root in customer_roots:
        if not root.exists():
            continue
        if root.is_file():
            if _path_contains_shadow_collision(root):
                collisions.append(root)
            continue
        for candidate in root.rglob("*"):
            if candidate.exists() and candidate.is_file() and _path_contains_shadow_collision(candidate):
                collisions.append(candidate)
    return _dedupe_paths(collisions)


def _promotion_is_unapproved(path: Path) -> bool:
    payload = _read_json(path)
    if not payload:
        return False
    active_updated = bool(payload.get("active_updated"))
    active_write_allowed = bool(payload.get("active_write_allowed"))
    requested = str(payload.get("requested_action") or "").lower()
    dry_run = bool(payload.get("dry_run", "dry-run" in path.name.lower() or "dry_run" in path.name.lower()))
    if active_updated or active_write_allowed:
        return True
    if requested and requested not in {"promotion_dry_run_only", "dry_run", "promotion_dry_run"}:
        return True
    return not dry_run and str(payload.get("status") or "").lower() in {"pass", "passed", "success"}


def detect_unapproved_artifacts() -> list[dict[str, Any]]:
    artifacts: list[dict[str, Any]] = []
    for path in _dedupe_paths(_active_model_paths()):
        if path.exists():
            artifacts.append(
                _artifact(
                    path,
                    "active_model_json",
                    "active_model_json_exists_without_current_approval",
                    "simulation_only_quarantine_then_refresh_registry_safety",
                )
            )
    for path in _dedupe_paths(_registry_active_pointer_paths()):
        if path.exists():
            artifacts.append(
                _artifact(
                    path,
                    "registry_active_pointer",
                    "registry_active_pointer_exists_without_current_approval",
                    "simulation_only_quarantine_then_require_human_registry_review",
                )
            )
    customer_paths = _dedupe_paths(_customer_prediction_paths())
    for path in customer_paths:
        if not path.exists():
            continue
        artifact_type = "customer_predictions_dir" if path.is_dir() else "customer_predictions_json"
        artifacts.append(
            _artifact(
                path,
                artifact_type,
                "customer_prediction_artifact_exists_in_research_only_state",
                "simulation_only_quarantine_then_verify_customer_prediction_boundary",
            )
        )
    for path in _scan_shadow_collisions(customer_paths):
        artifacts.append(
            _artifact(
                path,
                "shadow_output_customer_prediction_collision",
                "shadow_output_appears_under_customer_predictions_path",
                "simulation_only_quarantine_and_fix_shadow_output_path_contract",
            )
        )
    for active_dir in _dedupe_paths(_registry_active_dirs()):
        if not active_dir.exists():
            continue
        for path in _dedupe_paths([item for item in active_dir.rglob("*") if item.is_file()]):
            artifacts.append(
                _artifact(
                    path,
                    "model_registry_active_directory_artifact",
                    "unexpected_model_registry_active_directory_artifact",
                    "simulation_only_quarantine_then_refresh_model_registry_safety",
                )
            )
    for path in _dedupe_paths(_promotion_artifact_candidates()):
        if _promotion_is_unapproved(path):
            artifacts.append(
                _artifact(
                    path,
                    "unapproved_promotion_artifact",
                    "promotion_artifact_indicates_non_dry_run_or_active_write",
                    "simulation_only_quarantine_then_refresh_promotion_dry_run_evidence",
                )
            )
    # Dedupe by artifact type and original path after recursive customer scans.
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for item in artifacts:
        unique[(str(item.get("artifact_type")), str(item.get("original_path")))] = item
    return list(unique.values())


def validate_quarantine_manifest(manifest: Mapping[str, Any]) -> dict[str, Any]:
    actions = manifest.get("actions") if isinstance(manifest.get("actions"), list) else []
    blocking: list[str] = []
    if not bool(manifest.get("simulation_only")):
        blocking.append("manifest_must_be_simulation_only")
    for index, action in enumerate(actions):
        if not isinstance(action, Mapping):
            blocking.append(f"action_{index}_invalid")
            continue
        for field in ("original_path", "artifact_type", "reason", "recommended_action"):
            if not str(action.get(field) or "").strip():
                blocking.append(f"action_{index}_{field}_missing")
        if not bool(action.get("simulation_only")):
            blocking.append(f"action_{index}_must_be_simulation_only")
    return _safe_payload(
        {
            "status": "pass" if not blocking else "fail",
            "blocking_reasons": blocking,
        }
    )


def simulate_artifact_quarantine(
    *,
    artifacts: Sequence[Mapping[str, Any]] | None = None,
    write: bool = True,
    record_run: bool = True,
) -> dict[str, Any]:
    detected = [dict(item) for item in artifacts] if artifacts is not None else detect_unapproved_artifacts()
    actions = [
        {
            "original_path": item.get("original_path", ""),
            "artifact_type": item.get("artifact_type", "unknown"),
            "reason": item.get("reason", "unapproved_artifact_detected"),
            "recommended_action": item.get("recommended_action", "simulation_only_quarantine"),
            "simulation_only": True,
            "delete_performed": False,
            "move_performed": False,
        }
        for item in detected
    ]
    manifest = {
        "status": "ready" if not actions else "quarantine_simulated",
        "generated_at": _now(),
        "manifest_version": ROLLBACK_REHEARSAL_VERSION,
        "simulation_only": True,
        "quarantine_needed": bool(actions),
        "artifacts_detected": detected,
        "actions": actions,
        "simulated_quarantine_actions": actions,
        "rollback_plan": _rollback_plan(),
        "manual_actions_required": _manual_actions_required(bool(actions)),
        "safety_checks": _safety_checks(detected),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "manifest_path": str(_quarantine_manifest_path()),
        "report_path": str(_report_path()),
    }
    safe = _safe_payload(manifest)
    if write:
        _write_json(_quarantine_manifest_path(), safe)
    if record_run:
        run = start_research_run(
            service_name="rollback_artifact_quarantine_simulation",
            run_type="safe_dry_run",
            output_paths=[str(_quarantine_manifest_path())],
        )
        append_run_ledger(finalize_research_run(run, error_summary="artifact quarantine simulated" if actions else ""))
    return safe


def _rollback_plan() -> list[str]:
    return [
        "freeze governance actions",
        "disable active write",
        "quarantine unapproved artifacts",
        "rerun secret scan",
        "refresh registry safety",
        "refresh incident drill",
        "refresh post-release monitoring spec",
        "refresh decision board",
        "require human review before unlocking",
    ]


def _manual_actions_required(quarantine_needed: bool) -> list[str]:
    if quarantine_needed:
        return [
            "quarantine_unapproved_artifacts",
            "rerun_secret_scan",
            "refresh_registry_safety",
            "refresh_incident_drill",
            "refresh_decision_board",
            "complete_human_review_before_unlocking",
        ]
    return ["review_rehearsal_report", "keep_rollback_plan_current"]


def _monitoring_sentinel_flags() -> dict[str, bool]:
    path = _candidate_path("model_research/post_release_monitoring_spec_report.json")
    payload = _read_json(path)
    sentinels = payload.get("prediction_drift_sentinels") if isinstance(payload.get("prediction_drift_sentinels"), list) else []
    ids = {str(item.get("id") or "") for item in sentinels if isinstance(item, Mapping)}
    return {
        "monitoring_sentinel_defined_for_unexpected_active": "active_model_unexpected_existence" in ids,
        "monitoring_sentinel_defined_for_customer_prediction_path": "customer_prediction_path_violation" in ids,
    }


def _safety_checks(artifacts: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    types = {str(item.get("artifact_type") or "") for item in artifacts}
    sentinel_flags = _monitoring_sentinel_flags()
    return _safe_payload(
        {
            "active_model_json_absent": "active_model_json" not in types,
            "customer_predictions_absent": not any(
                item in types
                for item in (
                    "customer_predictions_dir",
                    "customer_predictions_json",
                    "shadow_output_customer_prediction_collision",
                )
            ),
            "active_write_allowed": False,
            "customer_prediction_write_allowed": False,
            **sentinel_flags,
        }
    )


def build_rollback_rehearsal_report(*, write: bool = True, record_run: bool = True) -> dict[str, Any]:
    artifacts = detect_unapproved_artifacts()
    manifest = simulate_artifact_quarantine(artifacts=artifacts, write=True, record_run=False)
    validation = validate_quarantine_manifest(manifest)
    quarantine_needed = bool(artifacts)
    blocking = []
    if quarantine_needed:
        blocking.append("unapproved_artifacts_detected")
    if validation.get("status") != "pass":
        blocking.extend(validation.get("blocking_reasons") or ["quarantine_manifest_invalid"])
    report = {
        "status": "blocked" if blocking else "ready",
        "generated_at": _now(),
        "rollback_rehearsal_version": ROLLBACK_REHEARSAL_VERSION,
        "quarantine_needed": quarantine_needed,
        "artifacts_detected": artifacts,
        "simulated_quarantine_actions": manifest.get("actions", []),
        "quarantine_manifest": manifest,
        "rollback_plan": _rollback_plan(),
        "manual_actions_required": _manual_actions_required(quarantine_needed),
        "safety_checks": _safety_checks(artifacts),
        **_linked_paths(),
        "blocking_reasons": blocking,
        "warning_reasons": [] if not quarantine_needed else ["quarantine_is_simulation_only_no_files_moved"],
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
            service_name="rollback_rehearsal",
            run_type="report_write",
            output_paths=[str(_report_path()), str(_quarantine_manifest_path())],
        )
        append_run_ledger(finalize_research_run(run, error_summary="artifact quarantine needed" if quarantine_needed else ""))
    return safe


def build_rollback_rehearsal_plan() -> dict[str, Any]:
    return build_rollback_rehearsal_report(write=True, record_run=True)


def get_latest_rollback_rehearsal_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if payload:
        return _safe_payload(payload)
    return build_rollback_rehearsal_report(write=False, record_run=False)
