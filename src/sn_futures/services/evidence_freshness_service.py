from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .evidence_bundle_service import collect_evidence_files


FRESHNESS_VERSION = "evidence_freshness_v1"
REPORT_FILENAME = "evidence_freshness_report.json"
TIMESTAMP_FIELDS = (
    "generated_at",
    "report_generated_at",
    "status_generated_at",
    "data_generated_at",
    "built_at",
    "created_at",
    "updated_at",
    "scanned_at",
)
DEFAULT_MAX_AGE_HOURS_BY_REPORT_TYPE: dict[str, int] = {
    "managed_proxy_config_wizard": 24,
    "managed_proxy_setup": 24,
    "managed_proxy_health": 24,
    "managed_proxy_schema_mapping": 24,
    "managed_pit_replay": 24,
    "managed_proxy_reliability": 24,
    "managed_data_quality": 24,
    "managed_data_audit": 24,
    "feature_store_v12_manifest": 72,
    "training_dataset_v12_manifest": 72,
    "candidate_v10_report": 168,
    "candidate_v12_report": 168,
    "year_concentration_evidence": 168,
    "cost_stress_attribution": 168,
    "v10_cost_remediation": 168,
    "research_decision_board": 24,
    "evidence_bundle": 24,
    "cpcv_report": 168,
}
TIMESTAMP_DEPENDENCIES: tuple[tuple[str, str], ...] = (
    ("managed_proxy_config_wizard", "managed_proxy_setup"),
    ("managed_proxy_setup", "managed_proxy_health"),
    ("managed_proxy_setup", "managed_proxy_schema_mapping"),
    ("managed_proxy_schema_mapping", "managed_proxy_health"),
    ("managed_proxy_health", "managed_proxy_reliability"),
    ("managed_proxy_health", "managed_pit_replay"),
    ("managed_pit_replay", "managed_data_audit"),
    ("managed_proxy_health", "managed_data_audit"),
    ("managed_data_audit", "feature_store_v12_manifest"),
    ("managed_pit_replay", "feature_store_v12_manifest"),
    ("managed_data_quality", "feature_store_v12_manifest"),
    ("feature_store_v12_manifest", "training_dataset_v12_manifest"),
    ("training_dataset_v12_manifest", "candidate_v12_report"),
    ("candidate_v12_report", "year_concentration_evidence"),
    ("candidate_v12_report", "cost_stress_attribution"),
    ("candidate_v12_report", "research_decision_board"),
    ("training_dataset_v12_manifest", "research_decision_board"),
    ("feature_store_v12_manifest", "research_decision_board"),
    ("research_decision_board", "evidence_bundle"),
)
V12_UPSTREAM_REPORTS = {
    "managed_data_audit",
    "managed_pit_replay",
    "managed_data_quality",
    "feature_store_v12_manifest",
    "training_dataset_v12_manifest",
    "candidate_v12_report",
}


def _now_dt() -> datetime:
    return datetime.now()


def _now() -> str:
    return _now_dt().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _report_path() -> Path:
    path = _output_dir() / "model_research" / REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


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


def _parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is not None:
        parsed = parsed.astimezone(timezone.utc).replace(tzinfo=None)
    return parsed


def _timestamp_from_payload(payload: Mapping[str, Any]) -> tuple[str, str]:
    for field in TIMESTAMP_FIELDS:
        value = payload.get(field)
        if value:
            return str(value), field
    return "", ""


def _status(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    return str(payload.get("status") or "missing").lower()


def _version_fields(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        return {}
    keys = (
        "candidate_version",
        "dataset_version",
        "training_dataset_version",
        "feature_store_version",
        "feature_store_status",
        "training_dataset_status",
        "audit_version",
        "replay_version",
        "quality_version",
    )
    return {key: payload.get(key) for key in keys if payload.get(key) is not None}


def collect_evidence_timestamps() -> dict[str, dict[str, Any]]:
    timestamps: dict[str, dict[str, Any]] = {}
    for name, item in collect_evidence_files().items():
        path = Path(str(item.get("path") or ""))
        payload = _read_json(path)
        generated_at = ""
        timestamp_field = ""
        timestamp_status = "report_missing"
        parsed: datetime | None = None
        if isinstance(payload, Mapping):
            generated_at, timestamp_field = _timestamp_from_payload(payload)
            parsed = _parse_dt(generated_at)
            if not generated_at:
                timestamp_status = "missing"
            elif parsed is None:
                timestamp_status = "invalid"
            else:
                timestamp_status = "present"
        timestamps[name] = {
            "name": name,
            "path": str(path),
            "exists": bool(item.get("exists")),
            "status": _status(payload),
            "generated_at": generated_at,
            "timestamp_field": timestamp_field,
            "timestamp_status": timestamp_status,
            "parsed_timestamp": parsed.isoformat(timespec="seconds") if parsed else "",
            "version_fields": _version_fields(payload),
            "max_allowed_age_hours": DEFAULT_MAX_AGE_HOURS_BY_REPORT_TYPE.get(name, 24),
        }
    return sanitize_for_json(timestamps)


def compute_report_age(generated_at: Any, *, now: datetime | None = None) -> float | None:
    parsed = _parse_dt(generated_at)
    if parsed is None:
        return None
    current = now or _now_dt()
    if current.tzinfo is not None:
        current = current.astimezone(timezone.utc).replace(tzinfo=None)
    return round((current - parsed).total_seconds() / 3600, 4)


def _timestamp_for(entry: Mapping[str, Any]) -> datetime | None:
    return _parse_dt(entry.get("generated_at") or entry.get("parsed_timestamp"))


def detect_stale_reports(timestamps: Mapping[str, Mapping[str, Any]], *, now: datetime | None = None) -> list[str]:
    stale: list[str] = []
    for name, entry in timestamps.items():
        if entry.get("timestamp_status") != "present":
            continue
        age = compute_report_age(entry.get("generated_at"), now=now)
        max_age = float(entry.get("max_allowed_age_hours") or DEFAULT_MAX_AGE_HOURS_BY_REPORT_TYPE.get(str(name), 24))
        if age is not None and age > max_age:
            stale.append(str(name))
    return sorted(stale)


def _report_age_table(timestamps: Mapping[str, Mapping[str, Any]], *, now: datetime | None = None) -> dict[str, dict[str, Any]]:
    stale = set(detect_stale_reports(timestamps, now=now))
    table: dict[str, dict[str, Any]] = {}
    for name, entry in timestamps.items():
        age = compute_report_age(entry.get("generated_at"), now=now)
        table[name] = {
            "generated_at": entry.get("generated_at") or "",
            "timestamp_field": entry.get("timestamp_field") or "",
            "timestamp_status": entry.get("timestamp_status") or "missing",
            "age_hours": age,
            "max_allowed_age_hours": entry.get("max_allowed_age_hours") or DEFAULT_MAX_AGE_HOURS_BY_REPORT_TYPE.get(name, 24),
            "stale": name in stale,
            "status": entry.get("status") or "missing",
            "path": entry.get("path") or "",
        }
    return sanitize_for_json(table)


def detect_upstream_downstream_timestamp_inversion(timestamps: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    inversions: list[dict[str, Any]] = []
    for upstream, downstream in TIMESTAMP_DEPENDENCIES:
        upstream_entry = timestamps.get(upstream)
        downstream_entry = timestamps.get(downstream)
        if not isinstance(upstream_entry, Mapping) or not isinstance(downstream_entry, Mapping):
            continue
        upstream_ts = _timestamp_for(upstream_entry)
        downstream_ts = _timestamp_for(downstream_entry)
        if upstream_ts is None or downstream_ts is None:
            continue
        if downstream_ts < upstream_ts:
            inversions.append(
                {
                    "upstream": upstream,
                    "downstream": downstream,
                    "upstream_generated_at": upstream_ts.isoformat(timespec="seconds"),
                    "downstream_generated_at": downstream_ts.isoformat(timespec="seconds"),
                    "age_gap_hours": round((upstream_ts - downstream_ts).total_seconds() / 3600, 4),
                }
            )
    return sanitize_for_json(inversions)


def _field(entry: Mapping[str, Any], key: str) -> str:
    version_fields = entry.get("version_fields")
    if isinstance(version_fields, Mapping):
        return str(version_fields.get(key) or "")
    return ""


def detect_cross_report_version_mismatch(timestamps: Mapping[str, Mapping[str, Any]]) -> list[dict[str, Any]]:
    mismatches: list[dict[str, Any]] = []
    fs = timestamps.get("feature_store_v12_manifest") or {}
    td = timestamps.get("training_dataset_v12_manifest") or {}
    candidate = timestamps.get("candidate_v12_report") or {}

    fs_version = _field(fs, "feature_store_version")
    td_fs_version = _field(td, "feature_store_version")
    if fs_version and td_fs_version and fs_version != td_fs_version:
        mismatches.append(
            {
                "report": "training_dataset_v12_manifest",
                "field": "feature_store_version",
                "expected_from": "feature_store_v12_manifest",
                "expected": fs_version,
                "actual": td_fs_version,
            }
        )

    td_version = _field(td, "dataset_version") or _field(td, "training_dataset_version")
    candidate_td_version = _field(candidate, "dataset_version") or _field(candidate, "training_dataset_version")
    if td_version and candidate_td_version and td_version != candidate_td_version:
        mismatches.append(
            {
                "report": "candidate_v12_report",
                "field": "dataset_version",
                "expected_from": "training_dataset_v12_manifest",
                "expected": td_version,
                "actual": candidate_td_version,
            }
        )

    candidate_fs_version = _field(candidate, "feature_store_version")
    if fs_version and candidate_fs_version and fs_version != candidate_fs_version:
        mismatches.append(
            {
                "report": "candidate_v12_report",
                "field": "feature_store_version",
                "expected_from": "feature_store_v12_manifest",
                "expected": fs_version,
                "actual": candidate_fs_version,
            }
        )
    return sanitize_for_json(mismatches)


def _blocking_reasons(
    *,
    timestamps: Mapping[str, Mapping[str, Any]],
    stale_reports: list[str],
    timestamp_inversions: list[Mapping[str, Any]],
    version_mismatches: list[Mapping[str, Any]],
) -> list[str]:
    reasons: list[str] = []
    for name, entry in timestamps.items():
        status = str(entry.get("timestamp_status") or "")
        if status == "missing":
            reasons.append(f"freshness:{name}_missing_generated_at")
        elif status == "invalid":
            reasons.append(f"freshness:{name}_invalid_generated_at")
        elif status == "report_missing":
            reasons.append(f"freshness:{name}_report_missing")
    reasons.extend(f"freshness:{name}_stale" for name in stale_reports)
    reasons.extend(
        f"freshness:{item.get('downstream')}_older_than_{item.get('upstream')}"
        for item in timestamp_inversions
        if item.get("upstream") and item.get("downstream")
    )
    reasons.extend(
        f"freshness:{item.get('report')}_{item.get('field')}_mismatch"
        for item in version_mismatches
        if item.get("report") and item.get("field")
    )
    seen: set[str] = set()
    out: list[str] = []
    for reason in reasons:
        if reason not in seen:
            seen.add(reason)
            out.append(reason)
    return out


def build_evidence_freshness_report(*, now: datetime | None = None, write: bool = True) -> dict[str, Any]:
    current = now or _now_dt()
    timestamps = collect_evidence_timestamps()
    stale_reports = detect_stale_reports(timestamps, now=current)
    timestamp_inversions = detect_upstream_downstream_timestamp_inversion(timestamps)
    version_mismatches = detect_cross_report_version_mismatch(timestamps)
    missing_timestamps = sorted(
        name
        for name, entry in timestamps.items()
        if str(entry.get("timestamp_status") or "") in {"missing", "invalid"}
    )
    missing_reports = sorted(
        name
        for name, entry in timestamps.items()
        if str(entry.get("timestamp_status") or "") == "report_missing"
    )
    blocking_reasons = _blocking_reasons(
        timestamps=timestamps,
        stale_reports=stale_reports,
        timestamp_inversions=timestamp_inversions,
        version_mismatches=version_mismatches,
    )
    warning_reasons = [f"freshness:{name}_report_missing" for name in missing_reports]
    status = "blocked" if blocking_reasons else "ready"
    payload = {
        "status": status,
        "generated_at": current.isoformat(timespec="seconds"),
        "freshness_version": FRESHNESS_VERSION,
        "report_ages": _report_age_table(timestamps, now=current),
        "stale_reports": stale_reports,
        "missing_reports": missing_reports,
        "missing_timestamps": missing_timestamps,
        "version_mismatches": version_mismatches,
        "timestamp_inversions": timestamp_inversions,
        "max_allowed_age_hours_by_report_type": DEFAULT_MAX_AGE_HOURS_BY_REPORT_TYPE,
        "blocking_reasons": blocking_reasons,
        "warning_reasons": warning_reasons,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    return _write_json(_report_path(), payload) if write else sanitize_for_json(payload)


def get_evidence_freshness_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_evidence_freshness_report(write=False)


def _is_v12_freshness_blocked(freshness: Mapping[str, Any]) -> bool:
    stale = set(str(item) for item in freshness.get("stale_reports") or [])
    missing_ts = set(str(item) for item in freshness.get("missing_timestamps") or [])
    if stale & V12_UPSTREAM_REPORTS or missing_ts & V12_UPSTREAM_REPORTS:
        return True
    for item in freshness.get("timestamp_inversions") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("upstream") or "") in V12_UPSTREAM_REPORTS or str(item.get("downstream") or "") in V12_UPSTREAM_REPORTS:
            return True
    for item in freshness.get("version_mismatches") or []:
        if not isinstance(item, Mapping):
            continue
        if str(item.get("report") or "") in V12_UPSTREAM_REPORTS:
            return True
    return False


def attach_freshness_to_decision_board(
    board: Mapping[str, Any],
    freshness: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    out = dict(board)
    payload = dict(freshness) if isinstance(freshness, Mapping) else get_evidence_freshness_report()
    summary = {
        "status": payload.get("status", "missing"),
        "generated_at": payload.get("generated_at"),
        "stale_reports": list(payload.get("stale_reports") or []),
        "missing_timestamps": list(payload.get("missing_timestamps") or []),
        "timestamp_inversions": list(payload.get("timestamp_inversions") or []),
        "version_mismatches": list(payload.get("version_mismatches") or []),
        "blocking_reasons": list(payload.get("blocking_reasons") or []),
        "report_path": payload.get("report_path"),
    }
    out["evidence_freshness_summary"] = sanitize_for_json(summary)
    if str(payload.get("status") or "").lower() != "blocked":
        return sanitize_for_json(out)

    freshness_blockers = [str(item) for item in payload.get("blocking_reasons") or [] if str(item or "").strip()]
    existing = [str(item) for item in out.get("blocking_reasons") or [] if str(item or "").strip()]
    merged = []
    seen: set[str] = set()
    for item in [*existing, *freshness_blockers]:
        if item not in seen:
            seen.add(item)
            merged.append(item)
    out["blocking_reasons"] = merged
    top: list[str] = []
    seen_top: set[str] = set()
    prioritized = [*existing[:8], *freshness_blockers, *merged]
    for item in prioritized:
        if item not in seen_top:
            seen_top.add(item)
            top.append(item)
    out["top_blocking_reasons"] = top[:12]
    out["manual_approval_recommended"] = False
    out["active_publish_allowed"] = False
    if _is_v12_freshness_blocked(payload):
        out["candidate_v12_allowed"] = False
        out["candidate_training_allowed"] = False
    if str(out.get("current_research_state") or "") in {"ready_for_manual_review", "active_publish_not_allowed"}:
        out["current_research_state"] = "evidence_freshness_blocked"
        out["next_allowed_action"] = "refresh_stale_evidence"
    warnings = [str(item) for item in out.get("warning_reasons") or [] if str(item or "").strip()]
    warnings.append("evidence_freshness_blocked")
    out["warning_reasons"] = sorted(set(warnings))
    out["status"] = "blocked"
    out["training_invoked"] = False
    out["active_updated"] = False
    out["customer_prediction_generated"] = False
    return sanitize_for_json(out)
