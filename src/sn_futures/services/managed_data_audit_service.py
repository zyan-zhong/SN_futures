from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from statistics import median
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS
from .managed_pit_replay_service import load_latest_pit_replay_report
from .managed_proxy_health_service import get_managed_proxy_health


AUDIT_VERSION = "pit_v1"
REQUIRED_TIMESTAMP_FIELDS = ("source_timestamp", "asof_date", "ingest_timestamp")
MANIFEST_FILENAME = "managed_data_audit_manifest.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _manifest_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / MANIFEST_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _managed_data_path() -> Path:
    return get_user_output_dir() / "fundamentals" / "managed_fundamentals.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_manifest(payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path = _manifest_path()
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    text = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(text).date()
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10] if fmt == "%Y-%m-%d" else text[:8], fmt).date()
        except Exception:
            continue
    return None


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("rows") or payload.get("data") or payload.get("history") or []
    else:
        rows = payload
    if not isinstance(rows, list):
        return []
    return [dict(item) for item in rows if isinstance(item, Mapping)]


def _feature_date(row: Mapping[str, Any]) -> date | None:
    return _parse_date(row.get("feature_date") or row.get("trade_date") or row.get("date"))


def _prediction_cutoff(row: Mapping[str, Any]) -> date | None:
    return _parse_date(row.get("prediction_cutoff_date") or row.get("cutoff_date")) or _feature_date(row)


def _timestamp_coverage(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    by_field: dict[str, dict[str, Any]] = {}
    for field in REQUIRED_TIMESTAMP_FIELDS:
        present = sum(1 for row in rows if str(row.get(field) or "").strip())
        by_field[field] = {
            "present": present,
            "missing": max(total - present, 0),
            "coverage": round(present / total, 4) if total else 0.0,
        }
    complete_rows = sum(1 for row in rows if all(str(row.get(field) or "").strip() for field in REQUIRED_TIMESTAMP_FIELDS))
    return {
        "row_count": total,
        "complete_rows": complete_rows,
        "complete_ratio": round(complete_rows / total, 4) if total else 0.0,
        "by_field": by_field,
    }


def _fundamental_coverage(rows: list[Mapping[str, Any]]) -> tuple[list[str], list[str]]:
    available: set[str] = set()
    for field in MANAGED_REQUIRED_RESEARCH_FIELDS:
        if any(row.get(field) not in {None, ""} for row in rows):
            available.add(field)
    missing = sorted(set(MANAGED_REQUIRED_RESEARCH_FIELDS) - available)
    return sorted(available), missing


def detect_timestamp_leakage(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    source_late = 0
    asof_late = 0
    feature_cutoff_late = 0
    ingest_used_as_asof = 0
    for row in rows:
        feature = _feature_date(row)
        cutoff = _prediction_cutoff(row)
        source = _parse_date(row.get("source_timestamp"))
        asof = _parse_date(row.get("asof_date"))
        ingest = _parse_date(row.get("ingest_timestamp"))
        if source and cutoff and source > cutoff:
            source_late += 1
        if asof and ((feature and asof > feature) or (cutoff and asof > cutoff)):
            asof_late += 1
        if feature and cutoff and feature > cutoff:
            feature_cutoff_late += 1
        if not asof and ingest:
            ingest_used_as_asof += 1
    return {
        "source_timestamp_leakage_pass": source_late == 0,
        "asof_date_leakage_pass": asof_late == 0,
        "feature_date_cutoff_pass": feature_cutoff_late == 0,
        "ingest_timestamp_not_used_as_asof_pass": ingest_used_as_asof == 0,
        "point_in_time_join_ready": bool(rows) and source_late == 0 and asof_late == 0 and feature_cutoff_late == 0 and ingest_used_as_asof == 0,
        "source_timestamp_late_rows": source_late,
        "asof_date_late_rows": asof_late,
        "feature_date_after_cutoff_rows": feature_cutoff_late,
        "rows_missing_asof_but_with_ingest": ingest_used_as_asof,
    }


def summarize_managed_field_lag(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    lags: list[int] = []
    by_field_lags: dict[str, list[int]] = {field: [] for field in MANAGED_REQUIRED_RESEARCH_FIELDS}
    rows_with_negative = 0
    rows_with_missing = 0
    for row in rows:
        feature = _feature_date(row)
        asof = _parse_date(row.get("asof_date"))
        if not feature or not asof:
            rows_with_missing += 1
            continue
        lag = (feature - asof).days
        if lag < 0:
            rows_with_negative += 1
        lags.append(lag)
        for field in MANAGED_REQUIRED_RESEARCH_FIELDS:
            if row.get(field) not in {None, ""}:
                by_field_lags[field].append(lag)

    def stats(values: list[int]) -> dict[str, Any]:
        if not values:
            return {"min_lag_days": None, "median_lag_days": None, "max_lag_days": None, "count": 0}
        return {
            "min_lag_days": min(values),
            "median_lag_days": median(values),
            "max_lag_days": max(values),
            "count": len(values),
        }

    return {
        **stats(lags),
        "by_field": {field: stats(values) for field, values in by_field_lags.items()},
        "rows_with_negative_lag": rows_with_negative,
        "rows_with_missing_lag": rows_with_missing,
    }


def validate_managed_point_in_time_rows(rows: list[Mapping[str, Any]]) -> dict[str, Any]:
    clean_rows = [dict(row) for row in rows]
    missing_timestamp_fields = sorted(
        field
        for field in REQUIRED_TIMESTAMP_FIELDS
        if any(not str(row.get(field) or "").strip() for row in clean_rows) or not clean_rows
    )
    available_fundamental_fields, missing_fundamental_fields = _fundamental_coverage(clean_rows)
    leakage = detect_timestamp_leakage(clean_rows)
    lag_summary = summarize_managed_field_lag(clean_rows)
    blocking: list[str] = []
    if not clean_rows:
        blocking.append("managed_rows_missing")
    for field in missing_timestamp_fields:
        blocking.append(f"missing_{field}")
    if missing_fundamental_fields:
        blocking.append("managed_fundamental_fields_missing")
    if not leakage["source_timestamp_leakage_pass"]:
        blocking.append("source_timestamp_leakage")
    if not leakage["asof_date_leakage_pass"]:
        blocking.append("asof_date_leakage")
    if not leakage["feature_date_cutoff_pass"]:
        blocking.append("feature_date_cutoff_fail")
    if not leakage["ingest_timestamp_not_used_as_asof_pass"]:
        blocking.append("ingest_timestamp_cannot_replace_asof_date")
    if lag_summary["rows_with_negative_lag"]:
        blocking.append("negative_asof_lag")

    status = "pass" if not blocking else "blocked"
    return sanitize_for_json(
        {
            "status": status,
            "row_count": len(clean_rows),
            "required_timestamp_fields": list(REQUIRED_TIMESTAMP_FIELDS),
            "missing_timestamp_fields": missing_timestamp_fields,
            "required_fundamental_fields": list(MANAGED_REQUIRED_RESEARCH_FIELDS),
            "available_fundamental_fields": available_fundamental_fields,
            "missing_fundamental_fields": missing_fundamental_fields,
            "field_timestamp_coverage": _timestamp_coverage(clean_rows),
            "field_lag_summary": lag_summary,
            "leakage_checks": leakage,
            "blocking_reasons": sorted(set(blocking)),
        }
    )


def load_latest_managed_health() -> dict[str, Any]:
    return get_managed_proxy_health()


def build_managed_audit_manifest(rows: list[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    health = load_latest_managed_health()
    if rows is None:
        rows = _rows_from_payload(_read_json(_managed_data_path()))
    validation = validate_managed_point_in_time_rows(list(rows))
    replay = load_latest_pit_replay_report()
    replay_blocking = []
    if replay and replay.get("status") != "ready":
        replay_blocking = ["pit_replay_failed", *[str(item) for item in (replay.get("blocking_reasons") or [])]]
    health_blockers = list(health.get("blocking_reasons") or [])
    health_status = str(health.get("provider_status") or "")
    config_blocking = health_status in {"disabled", "token_missing", "base_url_missing", "endpoint_missing", "auth_failed", "endpoint_unreachable"}
    blocking = sorted(set(validation["blocking_reasons"] + replay_blocking + (health_blockers if config_blocking else [])))
    replay_ready = not replay or replay.get("status") == "ready"
    status = "ready" if validation["status"] == "pass" and replay_ready and not config_blocking else "blocked"
    payload = {
        "status": status,
        "audit_version": AUDIT_VERSION,
        "generated_at": _now(),
        "managed_proxy_status": {
            "status": health.get("status"),
            "provider_status": health.get("provider_status"),
            "enabled": bool(health.get("enabled")),
            "configured": bool(health.get("configured")),
            "endpoint_configured": bool(health.get("endpoint_configured")),
            "token_configured": bool(health.get("token_configured")),
            "token_masked": str(health.get("token_masked") or ""),
            "last_refresh_time": health.get("last_refresh_time"),
            "required_field_coverage": health.get("required_field_coverage"),
        },
        "row_count": validation["row_count"],
        "required_timestamp_fields": validation["required_timestamp_fields"],
        "missing_timestamp_fields": validation["missing_timestamp_fields"],
        "required_fundamental_fields": validation["required_fundamental_fields"],
        "missing_fundamental_fields": validation["missing_fundamental_fields"],
        "field_timestamp_coverage": validation["field_timestamp_coverage"],
        "field_lag_summary": validation["field_lag_summary"],
        "leakage_checks": validation["leakage_checks"],
        "pit_replay_summary": {
            "status": replay.get("status", "missing") if replay else "missing",
            "replay_version": replay.get("replay_version") if replay else None,
            "cases_run": replay.get("cases_run", 0) if replay else 0,
            "cases_passed": replay.get("cases_passed", 0) if replay else 0,
            "cases_failed": replay.get("cases_failed", 0) if replay else 0,
            "point_in_time_join_ready": bool(replay.get("point_in_time_join_ready")) if replay else False,
            "blocking_reasons": list(replay.get("blocking_reasons") or []) if replay else [],
            "report_path": replay.get("report_path") if replay else "",
        },
        "blocking_reasons": blocking,
        "managed_data_used": bool(status == "ready" and validation["row_count"] > 0),
        "fake_data_used": False,
        "mock_data_used": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "manifest_path": str(_manifest_path()),
        "message_zh": "managed point-in-time audit passed." if status == "ready" else "managed point-in-time audit blocked.",
    }
    return _write_manifest(payload)


def get_latest_managed_audit_manifest() -> dict[str, Any]:
    payload = _read_json(_manifest_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_managed_audit_manifest()


def compute_managed_audit_readiness() -> dict[str, Any]:
    manifest = get_latest_managed_audit_manifest()
    leakage = manifest.get("leakage_checks") if isinstance(manifest.get("leakage_checks"), Mapping) else {}
    ready = bool(
        manifest.get("status") == "ready"
        and not manifest.get("missing_timestamp_fields")
        and not manifest.get("missing_fundamental_fields")
        and all(
            bool(leakage.get(key))
            for key in (
                "source_timestamp_leakage_pass",
                "asof_date_leakage_pass",
                "feature_date_cutoff_pass",
                "ingest_timestamp_not_used_as_asof_pass",
                "point_in_time_join_ready",
            )
        )
        and (not isinstance(manifest.get("pit_replay_summary"), Mapping) or manifest.get("pit_replay_summary", {}).get("status") in {"ready", "missing"})
    )
    return sanitize_for_json(
        {
            "status": "ready" if ready else "blocked",
            "ready": ready,
            "v12_allowed": ready,
            "audit_version": manifest.get("audit_version"),
            "manifest_path": manifest.get("manifest_path"),
            "row_count": manifest.get("row_count"),
            "field_timestamp_coverage": manifest.get("field_timestamp_coverage"),
            "field_lag_summary": manifest.get("field_lag_summary"),
            "leakage_checks": leakage,
            "pit_replay_summary": manifest.get("pit_replay_summary") if isinstance(manifest.get("pit_replay_summary"), Mapping) else {},
            "missing_timestamp_fields": manifest.get("missing_timestamp_fields") or [],
            "missing_fundamental_fields": manifest.get("missing_fundamental_fields") or [],
            "blocking_reasons": manifest.get("blocking_reasons") or [],
            "managed_data_used": bool(manifest.get("managed_data_used")),
            "fake_data_used": False,
            "mock_data_used": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )
