from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping


SAFETY_VERSION = "model_registry_safety_v1"
REPORT_FILENAME = "model_registry_safety_report.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _registry_dir() -> Path:
    path = _output_dir() / "model_registry"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_path() -> Path:
    path = _output_dir() / "model_research" / REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _normalise_version(candidate_version: str | None) -> str:
    value = str(candidate_version or "v10").strip().lower()
    if value.startswith("candidate_"):
        value = value.replace("candidate_", "", 1)
    return value or "v10"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_payload(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = _safe_payload(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _first_existing(paths: Sequence[Path]) -> Path:
    for path in paths:
        if path.exists():
            return path
    return paths[0]


def _load(paths: Sequence[Path]) -> tuple[dict[str, Any], str, str]:
    selected = _first_existing(paths)
    payload = _read_json(selected)
    if isinstance(payload, Mapping):
        return dict(payload), str(selected), "present"
    return {}, str(selected), "missing"


def _status(payload: Mapping[str, Any] | None) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
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
    return [
        out / "model_registry" / "active_model.json",
        out / "models" / "active_model.json",
        Path("outputs") / "model_registry" / "active_model.json",
        Path("outputs") / "models" / "active_model.json",
    ]


def _active_release_audit_paths() -> list[Path]:
    out = _output_dir()
    return [
        out / "model_registry" / "active_release_audit.json",
        Path("outputs") / "model_registry" / "active_release_audit.json",
    ]


def _promotion_paths(candidate_version: str) -> list[Path]:
    version = _normalise_version(candidate_version)
    out = _output_dir()
    return [
        out / "model_registry" / (f"promotion_report_{version}.json" if version != "v1" else "promotion_report.json"),
        out / "model_research" / f"candidate_{version}" / f"promotion_dry_run_{version}.json",
        Path("outputs") / "model_registry" / (f"promotion_report_{version}.json" if version != "v1" else "promotion_report.json"),
        Path("outputs") / "model_research" / f"candidate_{version}" / f"promotion_dry_run_{version}.json",
    ]


def _candidate_report_paths(candidate_version: str) -> list[Path]:
    version = _normalise_version(candidate_version)
    out = _output_dir()
    return [
        out / "model_research" / f"candidate_{version}" / f"candidate_{version}_gated_research_report.json",
        Path("outputs") / "model_research" / f"candidate_{version}" / f"candidate_{version}_gated_research_report.json",
    ]


def _decision_board_paths() -> list[Path]:
    out = _output_dir()
    return [
        out / "model_research" / "research_decision_board.json",
        Path("outputs") / "model_research" / "research_decision_board.json",
    ]


def _run_ledger_paths() -> list[Path]:
    out = _output_dir()
    return [
        out / "model_research" / "run_ledger" / "research_run_ledger_report.json",
        Path("outputs") / "model_research" / "run_ledger" / "research_run_ledger_report.json",
    ]


def _promotion_passed(promotion_report: Mapping[str, Any]) -> bool:
    status = _status(promotion_report)
    passed = bool(promotion_report.get("passed") or status in {"pass", "passed", "success"})
    dry_run = bool(promotion_report.get("dry_run", True))
    active_updated = bool(promotion_report.get("active_updated"))
    return passed and dry_run and not active_updated


def _promotion_status(promotion_report: Mapping[str, Any]) -> str:
    if not promotion_report:
        return "missing"
    if _promotion_passed(promotion_report):
        return "pass"
    status = _status(promotion_report)
    if status in {"pass", "passed", "success"}:
        return "invalid"
    return status


def build_model_registry_safety_contract(*, candidate_version: str = "v10") -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    return _safe_payload(
        {
            "status": "defined",
            "contract_version": SAFETY_VERSION,
            "candidate_version": version,
            "approval_required": True,
            "active_publish_allowed_until_explicit_approval": False,
            "required_preconditions": [
                "manual_approval_recommended",
                "promotion_dry_run_pass",
                "rollback_target_available",
                "no_unapproved_active_model",
                "customer_prediction_generation_disabled",
            ],
            "forbidden_side_effects": [
                "write_active_model_json",
                "register_new_model",
                "copy_model_artifact",
                "generate_customer_prediction",
            ],
        }
    )


def _path_from_value(value: Any) -> Path | None:
    text = str(value or "").strip()
    if not text:
        return None
    path = Path(text)
    if not path.is_absolute():
        path = _output_dir() / text
    return path


def _rollback_candidates_from_audit(release_audit: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    candidates: list[dict[str, Any]] = []
    if not isinstance(release_audit, Mapping):
        return candidates
    for key in ("rollback_target_path", "previous_active_model_path", "rollback_model_path"):
        path = _path_from_value(release_audit.get(key))
        if path is not None:
            candidates.append({"source": f"audit:{key}", "path": str(path), "exists": path.exists()})
    rollback = release_audit.get("rollback_target")
    if isinstance(rollback, Mapping):
        path = _path_from_value(rollback.get("path"))
        if path is not None:
            candidates.append({"source": "audit:rollback_target", "path": str(path), "exists": path.exists()})
    return candidates


def _default_rollback_candidates(release_audit: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    registry = _registry_dir()
    candidates = [
        {"source": "registry", "path": str(registry / "rollback" / "active_model_previous.json"), "exists": (registry / "rollback" / "active_model_previous.json").exists()},
        {"source": "registry", "path": str(registry / "active_model_previous.json"), "exists": (registry / "active_model_previous.json").exists()},
        {"source": "registry", "path": str(registry / "rollback" / "latest_active_model.json"), "exists": (registry / "rollback" / "latest_active_model.json").exists()},
    ]
    candidates.extend(_rollback_candidates_from_audit(release_audit))
    return candidates


def validate_rollback_plan(*, rollback_candidates: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    candidates = [dict(item) for item in rollback_candidates or _default_rollback_candidates()]
    available = [item for item in candidates if bool(item.get("exists"))]
    return _safe_payload(
        {
            "status": "ready" if available else "blocked",
            "rollback_target_available": bool(available),
            "rollback_candidates": candidates,
            "selected_rollback_target": available[0] if available else {},
            "blocking_reasons": [] if available else ["rollback_target_missing"],
        }
    )


def detect_unapproved_active_model(
    *,
    active_model: Mapping[str, Any] | None = None,
    release_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    active_model = dict(active_model or {})
    release_audit = dict(release_audit or {})
    active_exists = bool(active_model)
    approved = bool(
        release_audit.get("status") == "active_released"
        and release_audit.get("active_updated") is True
        and release_audit.get("blocking_reasons") in ([], None)
    )
    unapproved = active_exists and not approved
    return _safe_payload(
        {
            "status": "violation" if unapproved else "pass",
            "current_active_model_exists": active_exists,
            "release_audit_exists": bool(release_audit),
            "unapproved_active_detected": unapproved,
            "blocking_reasons": ["unapproved_active_model_detected"] if unapproved else [],
        }
    )


def validate_active_write_preconditions(
    *,
    decision_board: Mapping[str, Any],
    promotion_report: Mapping[str, Any],
    rollback_plan: Mapping[str, Any],
    unapproved_active: Mapping[str, Any],
) -> dict[str, Any]:
    reasons: list[str] = []
    manual_ready = bool(decision_board.get("manual_approval_recommended"))
    if not manual_ready:
        reasons.append("manual_approval_not_recommended")
    if bool(decision_board.get("active_publish_allowed")):
        reasons.append("active_publish_already_allowed_without_registry_safety")
    if not _promotion_passed(promotion_report):
        reasons.append("promotion_dry_run_failed")
    if not bool(rollback_plan.get("rollback_target_available")):
        reasons.append("rollback_target_missing")
    if bool(unapproved_active.get("unapproved_active_detected")):
        reasons.append("unapproved_active_model_detected")
    reasons.append("active_publish_workflow_not_implemented")
    return _safe_payload(
        {
            "status": "blocked",
            "active_write_allowed": False,
            "blocking_reasons": sorted(set(reasons)),
            "approval_required": True,
        }
    )


def _load_active_model() -> tuple[dict[str, Any], str, bool]:
    path = _first_existing(_active_model_paths())
    payload = _read_json(path)
    return (dict(payload), str(path), True) if isinstance(payload, Mapping) else ({}, str(path), False)


def _load_release_audit() -> tuple[dict[str, Any], str, bool]:
    path = _first_existing(_active_release_audit_paths())
    payload = _read_json(path)
    return (dict(payload), str(path), True) if isinstance(payload, Mapping) else ({}, str(path), False)


def _load_inputs(candidate_version: str) -> dict[str, Any]:
    active, active_path, active_exists = _load_active_model()
    audit, audit_path, audit_exists = _load_release_audit()
    promotion, promotion_path, promotion_state = _load(_promotion_paths(candidate_version))
    candidate, candidate_path, candidate_state = _load(_candidate_report_paths(candidate_version))
    decision, decision_path, decision_state = _load(_decision_board_paths())
    run_ledger, run_ledger_path, run_ledger_state = _load(_run_ledger_paths())
    return {
        "active_model": active,
        "active_model_path": active_path,
        "active_model_exists": active_exists,
        "release_audit": audit,
        "release_audit_path": audit_path,
        "release_audit_exists": audit_exists,
        "promotion_report": promotion,
        "promotion_report_path": promotion_path,
        "promotion_report_state": promotion_state,
        "candidate_report": candidate,
        "candidate_report_path": candidate_path,
        "candidate_report_state": candidate_state,
        "decision_board": decision,
        "decision_board_path": decision_path,
        "decision_board_state": decision_state,
        "run_ledger": run_ledger,
        "run_ledger_path": run_ledger_path,
        "run_ledger_state": run_ledger_state,
    }


def build_registry_safety_report(*, candidate_version: str = "v10", write: bool = True) -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    inputs = _load_inputs(version)
    rollback = validate_rollback_plan(rollback_candidates=_default_rollback_candidates(inputs["release_audit"]))
    unapproved = detect_unapproved_active_model(active_model=inputs["active_model"], release_audit=inputs["release_audit"])
    preconditions = validate_active_write_preconditions(
        decision_board=inputs["decision_board"],
        promotion_report=inputs["promotion_report"],
        rollback_plan=rollback,
        unapproved_active=unapproved,
    )
    status = "violation" if unapproved["unapproved_active_detected"] else "blocked"
    payload = {
        "status": status,
        "generated_at": _now(),
        "safety_version": SAFETY_VERSION,
        "candidate_version": version,
        "report_path": str(_report_path()),
        "active_write_allowed": bool(preconditions["active_write_allowed"]),
        "approval_required": True,
        "rollback_target_available": bool(rollback["rollback_target_available"]),
        "current_active_model_exists": bool(inputs["active_model_exists"]),
        "unapproved_active_detected": bool(unapproved["unapproved_active_detected"]),
        "promotion_dry_run_status": _promotion_status(inputs["promotion_report"]),
        "rollback_plan": rollback,
        "active_model_path": inputs["active_model_path"],
        "active_release_audit_path": inputs["release_audit_path"],
        "promotion_report_path": inputs["promotion_report_path"],
        "candidate_report_path": inputs["candidate_report_path"],
        "decision_board_path": inputs["decision_board_path"],
        "run_ledger_status": inputs["run_ledger"].get("status", "missing"),
        "contract": build_model_registry_safety_contract(candidate_version=version),
        "preconditions": preconditions,
        "blocking_reasons": sorted(set(preconditions["blocking_reasons"] + rollback["blocking_reasons"] + unapproved["blocking_reasons"])),
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return _write_json(_report_path(), payload) if write else _safe_payload(payload)


def get_model_registry_safety_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return _safe_payload(dict(payload))
    return build_registry_safety_report(write=False)
