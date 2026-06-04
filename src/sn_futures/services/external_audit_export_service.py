from __future__ import annotations

import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import contains_secret_like_value, sanitize_text
from .research_run_ledger_service import append_run_ledger, finalize_research_run, start_research_run


AUDIT_EXPORT_VERSION = "external_audit_export_v1"
RAW_ROW_KEYS = {
    "rows",
    "data",
    "records",
    "managed_rows",
    "raw_rows",
    "customer_rows",
    "predictions",
    "customer_predictions",
    "oof_trace",
    "oof_rows",
    "trades",
}
REQUIRED_SOURCE_NAMES = ("research_decision_board", "evidence_bundle", "run_ledger")
OPTIONAL_SOURCE_PATHS: tuple[tuple[str, str], ...] = (
    ("evidence_freshness", "model_research/evidence_freshness_report.json"),
    ("governance_access_control", "model_research/governance_access_control_report.json"),
    ("incident_drill", "model_research/incident_drill_report.json"),
    ("manual_approval", "model_research/manual_approval_report.json"),
    ("shadow_output_contract", "model_research/shadow_output_contract_report.json"),
    ("model_registry_safety", "model_research/model_registry_safety_report.json"),
    ("governance_observability", "model_research/governance_observability_report.json"),
    ("readiness_dag", "model_research/readiness_dag_report.json"),
    ("governance_maturity_matrix", "model_research/governance_maturity_matrix.json"),
    ("model_card", "model_research/model_card.json"),
    ("managed_data_audit", "diagnostics/managed_data_audit_manifest.json"),
    ("managed_data_quality", "diagnostics/managed_data_quality_scorecard.json"),
)
SECRET_VALUE_RE = re.compile(r"(?i)(bearer\s+[A-Za-z0-9._\-]{8,}|authorization\s*[:=]\s*[^\s,;\"']+|token\s*[:=]\s*[^\s,;\"']+|secret\s*[:=]\s*[^\s,;\"']+)")
LONG_HEX_RE = re.compile(r"\b[a-fA-F0-9]{32,}\b")
URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _export_root() -> Path:
    path = _output_dir() / "governance" / "external_audit_export"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _audit_index_path() -> Path:
    return _export_root() / "audit_index.json"


def _review_summary_path() -> Path:
    return _export_root() / "review_summary.md"


def _evidence_manifest_path() -> Path:
    return _export_root() / "evidence_file_manifest.json"


def _hash_manifest_path() -> Path:
    return _export_root() / "hash_manifest.json"


def _redaction_report_path() -> Path:
    return _export_root() / "redaction_report.json"


def _read_json(path: Path) -> Any:
    if not path.exists() or not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(sanitize_text(text), encoding="utf-8")


def _resolve_output_path(relative_path: str) -> Path:
    primary = _output_dir() / relative_path
    if primary.exists():
        return primary
    fallback = Path("outputs") / relative_path
    if fallback.exists():
        return fallback
    return primary


def _source_paths() -> dict[str, Path]:
    required = {
        "research_decision_board": _resolve_output_path("model_research/research_decision_board.json"),
        "evidence_bundle": _resolve_output_path("model_research/evidence_bundle_index.json"),
        "run_ledger": _resolve_output_path("model_research/run_ledger/research_run_ledger_report.json"),
    }
    optional = {name: _resolve_output_path(relative_path) for name, relative_path in OPTIONAL_SOURCE_PATHS}
    return {**required, **optional}


def _hash_file(path: Path) -> dict[str, Any]:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return {"sha256": digest.hexdigest(), "size_bytes": int(path.stat().st_size), "exists": True}


def _status(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    return str(payload.get("status") or "missing").lower()


def _generated_at(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return ""
    for key in ("generated_at", "report_generated_at", "created_at", "updated_at"):
        value = payload.get(key)
        if value:
            return str(value)
    return ""


def _summary_from_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    keys = (
        "status",
        "generated_at",
        "current_research_state",
        "next_allowed_action",
        "blocking_reasons",
        "warning_reasons",
        "missing_reports",
        "incomplete_reports",
        "stale_reports",
        "violation_count",
        "ui_api_violations_count",
        "manual_approval_recommended",
        "active_publish_allowed",
        "training_invoked",
        "active_updated",
        "customer_prediction_generated",
        "report_path",
        "current_status",
        "intended_use",
        "prohibited_use",
        "gate_failures",
        "known_limitations",
        "model_card_md_path",
        "risk_disclosure_path",
        "production_readiness",
        "shadow_readiness",
        "critical_gaps",
        "recommended_prompt_sequence",
    )
    summary = {key: payload.get(key) for key in keys if key in payload}
    return redact_audit_payload(summary)["payload"]


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return any(fragment in lowered for fragment in ("token", "secret", "authorization", "api_key", "apikey", "password", "endpoint", "url", "base_url"))


def _redact_scalar(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    cleaned = sanitize_text(value)
    cleaned = URL_RE.sub("[redacted_endpoint]", cleaned)
    cleaned = LONG_HEX_RE.sub("***", cleaned)
    cleaned = SECRET_VALUE_RE.sub("***", cleaned)
    return cleaned


def _redact_recursive(payload: Any, *, path: str, redacted: list[str], omitted: list[str]) -> Any:
    if isinstance(payload, Mapping):
        out: dict[str, Any] = {}
        for raw_key, value in payload.items():
            key = str(raw_key)
            child_path = f"{path}.{key}" if path else key
            if key.lower() in RAW_ROW_KEYS:
                omitted.append(child_path)
                count = len(value) if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)) else None
                out[key] = {"omitted": True, "reason": "raw_rows_or_predictions_not_exported", "row_count": count}
                continue
            if _is_sensitive_key(key):
                redacted.append(child_path)
                if isinstance(value, bool):
                    out[key] = value
                elif value in ("", None):
                    out[key] = value
                else:
                    out[key] = "[redacted]"
                continue
            out[key] = _redact_recursive(value, path=child_path, redacted=redacted, omitted=omitted)
        return out
    if isinstance(payload, list):
        return [_redact_recursive(item, path=f"{path}[]", redacted=redacted, omitted=omitted) for item in payload[:20]]
    if isinstance(payload, str):
        cleaned = _redact_scalar(payload)
        if cleaned != payload:
            redacted.append(path or "value")
        return cleaned
    return payload


def redact_audit_payload(payload: Any) -> dict[str, Any]:
    redacted_fields: list[str] = []
    omitted_sensitive_files: list[str] = []
    cleaned = _redact_recursive(payload, path="", redacted=redacted_fields, omitted=omitted_sensitive_files)
    return sanitize_for_json(
        {
            "payload": cleaned,
            "redacted_fields": sorted(set(redacted_fields)),
            "omitted_sensitive_files": sorted(set(omitted_sensitive_files)),
        }
    )


def collect_audit_export_sources() -> dict[str, dict[str, Any]]:
    sources: dict[str, dict[str, Any]] = {}
    for name, path in _source_paths().items():
        payload = _read_json(path)
        exists = path.exists() and path.is_file()
        issue = ""
        if not exists:
            issue = "missing"
        elif not isinstance(payload, Mapping):
            issue = "incomplete"
        elif not payload.get("status") and name not in {"run_ledger"}:
            issue = "incomplete"
        stat = path.stat() if exists else None
        sources[name] = {
            "name": name,
            "path": str(path),
            "exists": exists,
            "status": _status(payload),
            "generated_at": _generated_at(payload),
            "issue": issue,
            "size_bytes": int(stat.st_size) if stat else 0,
            "summary": _summary_from_payload(payload),
        }
    return sanitize_for_json(sources)


def _walk_optional_sensitive_artifacts() -> dict[str, dict[str, Any]]:
    output = _output_dir()
    patterns = (
        ("oof_trace", "walk_forward/**/oof_trace*.csv"),
        ("managed_raw_rows", "managed_proxy/**/*.json"),
        ("managed_raw_rows", "fundamentals/managed_*.json"),
        ("customer_prediction", "customer_predictions*"),
    )
    artifacts: dict[str, dict[str, Any]] = {}
    for kind, pattern in patterns:
        for path in output.glob(pattern):
            if not path.is_file():
                continue
            key = f"{kind}:{path.name}:{len(artifacts)}"
            artifacts[key] = {
                "name": path.name,
                "path": str(path),
                "kind": kind,
                "omission_reason": f"{kind}_omitted",
                **_hash_file(path),
            }
    return sanitize_for_json(artifacts)


def compute_audit_file_hashes(paths_or_sources: Mapping[str, Any] | Sequence[Any]) -> dict[str, dict[str, Any]]:
    if isinstance(paths_or_sources, Mapping):
        iterator: Iterable[tuple[str, Any]] = paths_or_sources.items()
    else:
        iterator = ((str(item), item) for item in paths_or_sources)
    hashes: dict[str, dict[str, Any]] = {}
    for name, item in iterator:
        raw_path = item.get("path") if isinstance(item, Mapping) else item
        path = Path(str(raw_path or ""))
        if path.exists() and path.is_file():
            hashes[str(name)] = {"path": str(path), **_hash_file(path)}
        else:
            hashes[str(name)] = {"path": str(path), "sha256": "", "size_bytes": 0, "exists": False}
    return sanitize_for_json(hashes)


def _read_evidence_bundle() -> dict[str, Any]:
    payload = _read_json(_resolve_output_path("model_research/evidence_bundle_index.json"))
    return dict(payload) if isinstance(payload, Mapping) else {}


def _read_decision_board() -> dict[str, Any]:
    payload = _read_json(_resolve_output_path("model_research/research_decision_board.json"))
    return dict(payload) if isinstance(payload, Mapping) else {}


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


def _active_approved() -> bool:
    audit = _read_json(_resolve_output_path("model_registry/active_release_audit.json"))
    return isinstance(audit, Mapping) and str(audit.get("status") or "").lower() in {"approved", "active_released"} and bool(audit.get("active_updated"))


def _confirmation(paths: Sequence[Path], *, approved: bool = False) -> dict[str, Any]:
    existing = _existing(paths)
    return {"confirmed": not existing or approved, "existing_paths": existing, "approved": bool(approved)}


def validate_audit_export_no_secrets(payload: Any) -> dict[str, Any]:
    serialized = json.dumps(sanitize_for_json(payload), ensure_ascii=False, default=str)
    blocking: list[str] = []
    if contains_secret_like_value(serialized) or SECRET_VALUE_RE.search(serialized):
        blocking.append("secret_pattern_detected")
    if "Authorization" in serialized or "Bearer " in serialized:
        blocking.append("authorization_header_detected")
    return sanitize_for_json({"status": "pass" if not blocking else "fail", "blocking_reasons": sorted(set(blocking))})


def _merged_missing_reports(sources: Mapping[str, Mapping[str, Any]], evidence_bundle: Mapping[str, Any]) -> list[str]:
    missing = [name for name in REQUIRED_SOURCE_NAMES if sources.get(name, {}).get("issue") == "missing"]
    missing.extend(str(item) for item in evidence_bundle.get("missing_reports") or [])
    return sorted(set(missing))


def _merged_incomplete_reports(sources: Mapping[str, Mapping[str, Any]], evidence_bundle: Mapping[str, Any]) -> list[str]:
    incomplete = [name for name, source in sources.items() if source.get("issue") == "incomplete"]
    incomplete.extend(str(item) for item in evidence_bundle.get("incomplete_reports") or [])
    return sorted(set(incomplete))


def build_external_audit_index(*, write: bool = False) -> dict[str, Any]:
    sources = collect_audit_export_sources()
    evidence_bundle = _read_evidence_bundle()
    decision_board = _read_decision_board()
    source_hashes = compute_audit_file_hashes(sources)
    sensitive_artifacts = _walk_optional_sensitive_artifacts()
    sensitive_hashes = compute_audit_file_hashes(sensitive_artifacts)
    missing_reports = _merged_missing_reports(sources, evidence_bundle)
    incomplete_reports = _merged_incomplete_reports(sources, evidence_bundle)

    redaction_payload = redact_audit_payload({"sources": sources, "decision_board": decision_board, "evidence_bundle": evidence_bundle})
    redacted_fields = list(redaction_payload["redacted_fields"])
    omitted_sensitive_files = sorted(
        set(list(redaction_payload["omitted_sensitive_files"]) + [item.get("omission_reason", "sensitive_artifact_omitted") for item in sensitive_artifacts.values()])
    )
    active_confirmation = _confirmation(_active_model_paths(), approved=_active_approved())
    prediction_confirmation = _confirmation(_customer_prediction_paths(), approved=False)
    blocking_reasons: list[str] = []
    if missing_reports:
        blocking_reasons.append("missing_required_reports")
    if incomplete_reports:
        blocking_reasons.append("incomplete_required_reports")
    if not active_confirmation["confirmed"]:
        blocking_reasons.append("unapproved_active_model_present")
    if not prediction_confirmation["confirmed"]:
        blocking_reasons.append("unapproved_customer_predictions_present")

    current_state = str(decision_board.get("current_research_state") or evidence_bundle.get("current_research_state") or "missing")
    next_action = str(decision_board.get("next_allowed_action") or evidence_bundle.get("next_allowed_action") or "review_external_audit_export")
    evidence_files = {**sources, **{f"sensitive_artifact:{name}": item for name, item in sensitive_artifacts.items()}}
    payload = {
        "status": "violation" if any(reason.startswith("unapproved_") for reason in blocking_reasons) else ("incomplete" if blocking_reasons else "ready"),
        "generated_at": _now(),
        "audit_export_version": AUDIT_EXPORT_VERSION,
        "current_research_state": current_state,
        "next_allowed_action": next_action,
        "evidence_files": evidence_files,
        "evidence_file_count": sum(1 for item in evidence_files.values() if item.get("exists")),
        "file_hashes": {**source_hashes, **{f"sensitive_artifact:{name}": meta for name, meta in sensitive_hashes.items()}},
        "redacted_fields": sorted(set(redacted_fields)),
        "redacted_fields_count": len(set(redacted_fields)),
        "omitted_sensitive_files": omitted_sensitive_files,
        "missing_reports": missing_reports,
        "incomplete_reports": incomplete_reports,
        "blocking_reasons": sorted(set(blocking_reasons)),
        "active_model_confirmation": active_confirmation,
        "customer_prediction_confirmation": prediction_confirmation,
        "redaction_status": "pass",
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "export_root": str(_export_root()),
        "audit_index_path": str(_audit_index_path()),
        "review_summary_path": str(_review_summary_path()),
        "evidence_file_manifest_path": str(_evidence_manifest_path()),
        "hash_manifest_path": str(_hash_manifest_path()),
        "redaction_report_path": str(_redaction_report_path()),
    }
    secret_check = validate_audit_export_no_secrets(payload)
    if secret_check["status"] != "pass":
        payload["status"] = "violation"
        payload["redaction_status"] = "fail"
        payload["blocking_reasons"] = sorted(set(payload["blocking_reasons"] + list(secret_check["blocking_reasons"])))
    safe = sanitize_for_json(payload)
    if write:
        _write_json(_audit_index_path(), safe)
    return safe


def build_external_review_summary(index: Mapping[str, Any]) -> str:
    missing = list(index.get("missing_reports") or [])
    incomplete = list(index.get("incomplete_reports") or [])
    blockers = list(index.get("blocking_reasons") or [])
    evidence_names = sorted(str(name) for name in (index.get("evidence_files") or {}).keys())
    active_ok = bool((index.get("active_model_confirmation") or {}).get("confirmed")) if isinstance(index.get("active_model_confirmation"), Mapping) else False
    prediction_ok = bool((index.get("customer_prediction_confirmation") or {}).get("confirmed")) if isinstance(index.get("customer_prediction_confirmation"), Mapping) else False
    lines = [
        "# External Audit Review Summary",
        "",
        "## Current Status",
        f"- Status: {index.get('status', 'missing')}",
        f"- Current research state: {index.get('current_research_state', 'missing')}",
        f"- Next human action: {index.get('next_allowed_action', 'review_external_audit_export')}",
        "",
        "## Why System Is Blocked",
        *(f"- {reason}" for reason in (blockers or ["no current blockers in audit export"])),
        "",
        "## What Has Been Validated",
        "- Evidence paths and file hashes are indexed without copying raw rows.",
        "- Governance flags confirm no training, active write, or customer prediction generation by this export.",
        "- Sensitive fields are redacted before the review package is written.",
        "",
        "## What Has Not Been Validated",
        *(f"- Missing report: {item}" for item in missing),
        *(f"- Incomplete report: {item}" for item in incomplete),
        "" if missing or incomplete else "- No missing or incomplete reports were detected by the export layer.",
        "",
        "## No Active / No Prediction Confirmation",
        f"- active_model absent or approved: {active_ok}",
        f"- customer_predictions absent: {prediction_ok}",
        "",
        "## Key Evidence Report Names",
        *(f"- {name}" for name in evidence_names[:50]),
    ]
    return "\n".join(str(line) for line in lines if line is not None)


def write_external_audit_package() -> dict[str, Any]:
    index = build_external_audit_index(write=True)
    evidence_files = index.get("evidence_files") if isinstance(index.get("evidence_files"), Mapping) else {}
    file_hashes = index.get("file_hashes") if isinstance(index.get("file_hashes"), Mapping) else {}
    redaction_report = {
        "status": index.get("redaction_status", "missing"),
        "generated_at": index.get("generated_at", ""),
        "redacted_fields": index.get("redacted_fields", []),
        "redacted_fields_count": index.get("redacted_fields_count", 0),
        "omitted_sensitive_files": index.get("omitted_sensitive_files", []),
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    _write_json(_evidence_manifest_path(), {"evidence_files": evidence_files, "generated_at": _now()})
    _write_json(_hash_manifest_path(), {"file_hashes": file_hashes, "generated_at": _now()})
    _write_json(_redaction_report_path(), redaction_report)
    _write_text(_review_summary_path(), build_external_review_summary(index))

    run = start_research_run(
        service_name="external_audit_export",
        run_type="report_write",
        output_paths=[
            str(_audit_index_path()),
            str(_review_summary_path()),
            str(_evidence_manifest_path()),
            str(_hash_manifest_path()),
            str(_redaction_report_path()),
        ],
    )
    append_run_ledger(finalize_research_run(run))
    latest_index = _read_json(_audit_index_path())
    return sanitize_for_json(dict(latest_index) if isinstance(latest_index, Mapping) else index)


def get_external_audit_export() -> dict[str, Any]:
    payload = _read_json(_audit_index_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_external_audit_index(write=False)
