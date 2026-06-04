from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


BUNDLE_VERSION = "evidence_bundle_v1"
BUNDLE_FILENAME = "evidence_bundle_index.json"
TEXT_EVIDENCE_NAMES = {"model_card_md", "risk_disclosure"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _bundle_path() -> Path:
    path = _output_dir() / "model_research" / BUNDLE_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _evidence_path(relative_path: str) -> Path:
    primary = _output_dir() / relative_path
    if primary.exists():
        return primary
    fallback = Path("outputs") / relative_path
    if fallback.exists():
        return fallback
    return primary


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _evidence_paths() -> dict[str, Path]:
    return {
        "managed_proxy_operator_runbook": _evidence_path("diagnostics/managed_proxy_operator_runbook_report.json"),
        "managed_proxy_config_wizard": _evidence_path("diagnostics/managed_proxy_config_wizard_report.json"),
        "managed_proxy_setup": _evidence_path("diagnostics/managed_proxy_setup_report.json"),
        "managed_proxy_health": _evidence_path("diagnostics/managed_proxy_health.json"),
        "managed_proxy_schema_mapping": _evidence_path("diagnostics/managed_proxy_schema_mapping_report.json"),
        "managed_pit_replay": _evidence_path("diagnostics/managed_pit_replay_report.json"),
        "managed_proxy_reliability": _evidence_path("diagnostics/managed_proxy_reliability_report.json"),
        "managed_data_quality": _evidence_path("diagnostics/managed_data_quality_scorecard.json"),
        "managed_data_audit": _evidence_path("diagnostics/managed_data_audit_manifest.json"),
        "feature_store_v12_manifest": _evidence_path("feature_store/v12/feature_store_manifest.json"),
        "training_dataset_v12_manifest": _evidence_path("training_dataset_manifest_v12.json"),
        "candidate_v10_report": _evidence_path("model_research/candidate_v10/candidate_v10_gated_research_report.json"),
        "candidate_v12_report": _evidence_path("model_research/candidate_v12/candidate_v12_gated_research_report.json"),
        "year_concentration_evidence": _evidence_path("model_research/year_concentration_evidence.json"),
        "cost_stress_attribution": _evidence_path("model_research/cost_stress_attribution.json"),
        "v10_cost_remediation": _evidence_path("model_research/candidate_v10/v10_cost_failure_research_report.json"),
        "research_decision_board": _evidence_path("model_research/research_decision_board.json"),
        "governance_maturity_matrix": _evidence_path("model_research/governance_maturity_matrix.json"),
        "model_card_json": _evidence_path("model_research/model_card.json"),
        "model_card_md": _evidence_path("model_research/model_card.md"),
        "risk_disclosure": _evidence_path("model_research/risk_disclosure.md"),
        "cpcv_report": _evidence_path("validation/cpcv/cpcv_report.json"),
    }


def _status(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    return str(payload.get("status") or "missing").lower()


def _file_issue(name: str, path: Path, payload: Any) -> str:
    if not path.exists():
        return "missing"
    if name in TEXT_EVIDENCE_NAMES:
        try:
            if path.read_text(encoding="utf-8").strip():
                return ""
        except Exception:
            return "incomplete"
        return "incomplete"
    if not isinstance(payload, Mapping):
        return "incomplete"
    status = _status(payload)
    if status == "missing":
        return "incomplete"
    return ""


def collect_evidence_files() -> dict[str, dict[str, Any]]:
    files: dict[str, dict[str, Any]] = {}
    for name, path in _evidence_paths().items():
        payload = _read_json(path)
        issue = _file_issue(name, path, payload)
        stat = path.stat() if path.exists() else None
        files[name] = {
            "name": name,
            "path": str(path),
            "exists": path.exists(),
            "size_bytes": int(stat.st_size) if stat else 0,
            "modified_time": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds") if stat else "",
            "json_valid": isinstance(payload, Mapping),
            "status": _status(payload),
            "issue": issue,
        }
    return sanitize_for_json(files)


def validate_evidence_completeness(evidence_files: Mapping[str, Mapping[str, Any]]) -> dict[str, Any]:
    missing = sorted(name for name, item in evidence_files.items() if item.get("issue") == "missing")
    incomplete = sorted(name for name, item in evidence_files.items() if item.get("issue") == "incomplete")
    skipped_or_blocked = sorted(
        name
        for name, item in evidence_files.items()
        if str(item.get("status") or "").lower() in {"skipped", "blocked", "missing"}
        and item.get("exists")
    )
    return {
        "status": "complete" if not missing and not incomplete else "incomplete",
        "missing_reports": missing,
        "incomplete_reports": incomplete,
        "skipped_or_blocked_reports": skipped_or_blocked,
        "all_required_evidence_present": not missing and not incomplete,
    }


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def compute_evidence_hashes(evidence_files: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    hashes: dict[str, dict[str, Any]] = {}
    for name, item in evidence_files.items():
        path = Path(str(item.get("path") or ""))
        if not path.exists() or item.get("issue") == "missing":
            continue
        hashes[name] = {
            "sha256": _hash_file(path),
            "size_bytes": int(item.get("size_bytes") or 0),
            "status": item.get("status") or "missing",
        }
    return sanitize_for_json(hashes)


def _active_paths() -> list[Path]:
    out = _output_dir()
    return [
        out / "model_registry" / "active_model.json",
        out / "models" / "active_model.json",
        Path("outputs") / "model_registry" / "active_model.json",
        Path("outputs") / "models" / "active_model.json",
    ]


def _prediction_paths() -> list[Path]:
    out = _output_dir()
    return [
        out / "customer_predictions",
        out / "customer_predictions.json",
        Path("outputs") / "customer_predictions",
        Path("outputs") / "customer_predictions.json",
    ]


def _confirmation(paths: list[Path]) -> dict[str, Any]:
    existing = [str(path) for path in paths if path.exists()]
    return {"confirmed": not existing, "existing_paths": existing}


def _decision_board_payload() -> dict[str, Any]:
    payload = _read_json(_evidence_paths()["research_decision_board"])
    return dict(payload) if isinstance(payload, Mapping) else {}


def build_reproducibility_checklist(
    *,
    current_research_state: str,
    next_allowed_action: str,
    missing_reports: list[str],
    incomplete_reports: list[str],
    safety_flags: list[str],
) -> dict[str, Any]:
    blockers = [*missing_reports, *incomplete_reports]
    return {
        "code tests passed summary": "not embedded in bundle; rerun requested pytest groups for current verification.",
        "frontend tests passed summary": "not embedded in bundle; rerun npm typecheck/build/check/test for current verification.",
        "secret scan status": "not embedded in bundle; rerun scripts/scan_runtime_secrets.ps1 for current verification.",
        "current_blockers": blockers,
        "next_allowed_action": next_allowed_action or "review_missing_evidence",
        "required_human_manual_steps": [
            "Review missing and incomplete evidence reports.",
            "Run quality gate and secret scan before any release decision.",
            "Do not approve active unless candidate gates and manual approval phrase are explicitly satisfied.",
        ],
        "current_research_state": current_research_state or "unknown",
        "safety_flags": list(safety_flags),
        "all_required_evidence_present": not blockers,
    }


def _safety_flags(completeness: Mapping[str, Any], board: Mapping[str, Any], no_active: Mapping[str, Any], no_prediction: Mapping[str, Any]) -> list[str]:
    flags: list[str] = []
    if completeness.get("missing_reports"):
        flags.append("missing_reports")
    if completeness.get("incomplete_reports"):
        flags.append("incomplete_reports")
    if completeness.get("skipped_or_blocked_reports"):
        flags.append("skipped_or_blocked_reports")
    if not no_active.get("confirmed"):
        flags.append("active_model_present")
    else:
        flags.append("no_active_confirmed")
    if not no_prediction.get("confirmed"):
        flags.append("customer_prediction_present")
    else:
        flags.append("no_prediction_confirmed")
    if board and bool(board.get("manual_approval_recommended")):
        flags.append("manual_approval_review_required")
    return sorted(set(flags))


def build_evidence_bundle_index(*, write: bool = False) -> dict[str, Any]:
    evidence_files = collect_evidence_files()
    completeness = validate_evidence_completeness(evidence_files)
    hashes = compute_evidence_hashes(evidence_files)
    board = _decision_board_payload()
    current_state = str(board.get("current_research_state") or "missing")
    next_action = str(board.get("next_allowed_action") or "review_missing_evidence")
    no_active = _confirmation(_active_paths())
    no_prediction = _confirmation(_prediction_paths())
    safety_flags = _safety_flags(completeness, board, no_active, no_prediction)
    checklist = build_reproducibility_checklist(
        current_research_state=current_state,
        next_allowed_action=next_action,
        missing_reports=list(completeness["missing_reports"]),
        incomplete_reports=list(completeness["incomplete_reports"]),
        safety_flags=safety_flags,
    )
    blocked = bool(completeness["missing_reports"] or completeness["incomplete_reports"] or not no_active["confirmed"] or not no_prediction["confirmed"])
    payload = {
        "status": "blocked" if blocked else "ready",
        "generated_at": _now(),
        "bundle_version": BUNDLE_VERSION,
        "bundle_path": str(_bundle_path()),
        "current_research_state": current_state,
        "next_allowed_action": next_action,
        "evidence_files": evidence_files,
        "evidence_file_count": sum(1 for item in evidence_files.values() if item.get("exists")),
        "file_hashes": hashes,
        "missing_reports": completeness["missing_reports"],
        "incomplete_reports": completeness["incomplete_reports"],
        "skipped_or_blocked_reports": completeness["skipped_or_blocked_reports"],
        "reproducibility_checklist": checklist,
        "safety_flags": safety_flags,
        "no_active_confirmation": no_active,
        "no_prediction_confirmation": no_prediction,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return _write_json(_bundle_path(), payload) if write else sanitize_for_json(payload)


def write_evidence_bundle() -> dict[str, Any]:
    return build_evidence_bundle_index(write=True)


def get_latest_evidence_bundle() -> dict[str, Any]:
    payload = _read_json(_bundle_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_evidence_bundle_index(write=False)
