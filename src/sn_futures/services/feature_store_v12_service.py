from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .feature_store_service import _feature_store_manifest_path, _write_store_frame
from .feature_store_v10_service import build_feature_store_v10
from .managed_data_audit_service import compute_managed_audit_readiness
from .managed_data_quality_service import SCORECARD_FILENAME, get_latest_managed_data_quality_scorecard
from .managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS
from .managed_pit_replay_service import load_latest_pit_replay_report, run_pit_replay_harness
from .managed_proxy_health_service import get_managed_proxy_health
from .managed_proxy_schema_mapper_service import build_schema_mapping_report, get_schema_mapping_report


V12_FEATURE_SET = "managed_proxy_pit_gated_v12"
V12_REQUIRED_TIMESTAMP_FIELDS = (
    "source_timestamp",
    "asof_date",
    "ingest_timestamp",
    "feature_date",
    "prediction_cutoff_date",
)
V12_REQUIRED_FUNDAMENTAL_FIELDS = tuple(MANAGED_REQUIRED_RESEARCH_FIELDS)
V12_META_FIELDS = ("managed_asof_date", "managed_source_timestamp", "managed_ingest_timestamp")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _store_path() -> Path:
    path = get_user_output_dir() / "feature_store" / "v12" / "feature_store.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _managed_data_path() -> Path:
    return get_user_output_dir() / "fundamentals" / "managed_fundamentals.json"


def _quality_scorecard_path() -> Path:
    return get_user_output_dir() / "diagnostics" / SCORECARD_FILENAME


def _sample_fixture_report_path() -> Path:
    return get_user_output_dir() / "diagnostics" / "managed_proxy_sample_fixture_contract_report.json"


def _quarantine_snapshot_report_path() -> Path:
    return get_user_output_dir() / "diagnostics" / "managed_proxy_quarantine_snapshot_report.json"


def _quarantine_contract_report_path() -> Path:
    return get_user_output_dir() / "diagnostics" / "managed_proxy_quarantine_contract_report.json"


def _production_cache_gate_report_path() -> Path:
    return get_user_output_dir() / "diagnostics" / "managed_data_production_cache_gate_report.json"


def _v12_input_contract_report_path() -> Path:
    return get_user_output_dir() / "diagnostics" / "feature_store_v12_input_contract_report.json"


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


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("rows") or payload.get("data") or payload.get("history") or []
    else:
        rows = payload
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


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
            sample = text[:10] if fmt == "%Y-%m-%d" else text[:8]
            return datetime.strptime(sample, fmt).date()
        except Exception:
            continue
    return None


def _date_text(value: Any) -> str:
    parsed = _parse_date(value)
    return parsed.isoformat() if parsed else ""


def _managed_feature_date(row: Mapping[str, Any]) -> date | None:
    return _parse_date(row.get("feature_date") or row.get("trading_date"))


def _sample_feature_date(row: Mapping[str, Any]) -> date | None:
    return _parse_date(row.get("trade_date") or row.get("feature_date") or row.get("trading_date") or row.get("date"))


def _sample_cutoff_date(row: Mapping[str, Any]) -> date | None:
    return _parse_date(row.get("prediction_cutoff_date") or row.get("cutoff_date")) or _sample_feature_date(row)


def _managed_cutoff_date(row: Mapping[str, Any]) -> date | None:
    return _parse_date(row.get("prediction_cutoff_date") or row.get("cutoff_date"))


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _safe_health(health: Mapping[str, Any] | None) -> dict[str, Any]:
    health = health if isinstance(health, Mapping) else {}
    allowed = (
        "status",
        "provider_status",
        "enabled",
        "configured",
        "endpoint_configured",
        "token_configured",
        "token_masked",
        "token_source",
        "last_refresh_time",
        "last_success_time",
        "row_count",
        "from_cache",
        "required_fields",
        "available_fields",
        "missing_fields",
        "group_ready",
        "required_field_coverage",
        "blocking_reasons",
        "next_allowed_action",
        "v12_allowed",
        "ready",
        "no_fake_data",
        "generated_at",
        "message_zh",
        "error_message_zh",
    )
    return {key: health.get(key) for key in allowed if key in health}


def _safe_audit(audit: Mapping[str, Any] | None) -> dict[str, Any]:
    audit = audit if isinstance(audit, Mapping) else {}
    allowed = (
        "status",
        "ready",
        "v12_allowed",
        "audit_version",
        "manifest_path",
        "row_count",
        "field_timestamp_coverage",
        "field_lag_summary",
        "leakage_checks",
        "missing_timestamp_fields",
        "missing_fundamental_fields",
        "blocking_reasons",
        "managed_data_used",
        "fake_data_used",
        "mock_data_used",
        "training_invoked",
        "active_updated",
        "customer_prediction_generated",
    )
    return {key: audit.get(key) for key in allowed if key in audit}


def _field_coverage(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> dict[str, Any]:
    total_rows = len(rows)
    by_field: dict[str, dict[str, Any]] = {}
    available = 0
    for field in fields:
        if field == "feature_date":
            present = sum(1 for row in rows if _present(row.get("feature_date") or row.get("trading_date")))
        else:
            present = sum(1 for row in rows if _present(row.get(field)))
        if present:
            available += 1
        by_field[field] = {
            "present": present,
            "missing": max(total_rows - present, 0),
            "coverage": round(present / total_rows, 4) if total_rows else 0.0,
        }
    complete_rows = sum(
        1
        for row in rows
        if all(_present(row.get(field)) if field != "feature_date" else _present(row.get("feature_date") or row.get("trading_date")) for field in fields)
    )
    return {
        "total": len(fields),
        "available": available,
        "missing": max(len(fields) - available, 0),
        "ratio": round(available / len(fields), 4) if fields else 0.0,
        "label": f"{available}/{len(fields)}",
        "row_count": total_rows,
        "complete_rows": complete_rows,
        "complete_ratio": round(complete_rows / total_rows, 4) if total_rows else 0.0,
        "by_field": by_field,
    }


def _missing_timestamp_fields(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    if not rows:
        return list(V12_REQUIRED_TIMESTAMP_FIELDS)
    missing: list[str] = []
    for field in V12_REQUIRED_TIMESTAMP_FIELDS:
        if field == "feature_date":
            field_missing = any(not _present(row.get("feature_date") or row.get("trading_date")) for row in rows)
        else:
            field_missing = any(not _present(row.get(field)) for row in rows)
        if field_missing:
            missing.append(field)
    return missing


def _missing_fundamental_fields(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    missing = []
    for field in V12_REQUIRED_FUNDAMENTAL_FIELDS:
        if not rows or not any(_present(row.get(field)) for row in rows):
            missing.append(field)
    return missing


def _local_leakage_checks(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    source_late = 0
    asof_late = 0
    feature_after_cutoff = 0
    ingest_substitution = 0
    for row in rows:
        feature_date = _managed_feature_date(row)
        cutoff = _managed_cutoff_date(row)
        source = _parse_date(row.get("source_timestamp"))
        asof = _parse_date(row.get("asof_date"))
        ingest = _parse_date(row.get("ingest_timestamp"))
        if source and cutoff and source > cutoff:
            source_late += 1
        if asof and cutoff and asof > cutoff:
            asof_late += 1
        if feature_date and cutoff and feature_date > cutoff:
            feature_after_cutoff += 1
        if not asof and ingest:
            ingest_substitution += 1
    return {
        "source_timestamp_leakage_pass": source_late == 0,
        "asof_date_leakage_pass": asof_late == 0,
        "feature_date_cutoff_pass": feature_after_cutoff == 0,
        "ingest_timestamp_not_used_as_asof_pass": ingest_substitution == 0,
        "point_in_time_join_ready": bool(rows)
        and source_late == 0
        and asof_late == 0
        and feature_after_cutoff == 0
        and ingest_substitution == 0,
        "source_timestamp_late_rows": source_late,
        "asof_date_late_rows": asof_late,
        "feature_date_after_cutoff_rows": feature_after_cutoff,
        "rows_missing_asof_but_with_ingest": ingest_substitution,
    }


def load_latest_managed_health() -> dict[str, Any]:
    return get_managed_proxy_health()


def load_latest_managed_audit() -> dict[str, Any]:
    return compute_managed_audit_readiness()


def load_latest_schema_mapping() -> dict[str, Any]:
    return get_schema_mapping_report()


def load_latest_pit_replay() -> dict[str, Any]:
    return load_latest_pit_replay_report()


def _load_managed_rows() -> list[dict[str, Any]]:
    return _rows_from_payload(_read_json(_managed_data_path()))


def _health_status(health: Mapping[str, Any]) -> str:
    return str(health.get("provider_status") or health.get("status") or "missing")


def _audit_status(audit: Mapping[str, Any]) -> str:
    return str(audit.get("status") or "missing")


def _load_sample_fixture_report() -> dict[str, Any]:
    payload = _read_json(_sample_fixture_report_path())
    return sanitize_for_json(dict(payload)) if isinstance(payload, Mapping) else {}


def _load_quarantine_snapshot_report() -> dict[str, Any]:
    payload = _read_json(_quarantine_snapshot_report_path())
    return sanitize_for_json(dict(payload)) if isinstance(payload, Mapping) else {}


def _load_quarantine_contract_report() -> dict[str, Any]:
    payload = _read_json(_quarantine_contract_report_path())
    return sanitize_for_json(dict(payload)) if isinstance(payload, Mapping) else {}


def _load_production_cache_gate_report() -> dict[str, Any]:
    payload = _read_json(_production_cache_gate_report_path())
    return sanitize_for_json(dict(payload)) if isinstance(payload, Mapping) else {}


def _load_v12_input_contract_report() -> dict[str, Any]:
    payload = _read_json(_v12_input_contract_report_path())
    return sanitize_for_json(dict(payload)) if isinstance(payload, Mapping) else {}


def validate_v12_managed_readiness(
    *,
    health: Mapping[str, Any] | None = None,
    audit: Mapping[str, Any] | None = None,
    schema_mapping: Mapping[str, Any] | None = None,
    managed_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    rows = [dict(row) for row in (managed_rows if managed_rows is not None else _load_managed_rows())]
    health_payload = _safe_health(health if health is not None else load_latest_managed_health())
    audit_payload = _safe_audit(audit if audit is not None else load_latest_managed_audit())
    schema_mapping_payload = sanitize_for_json(
        dict(schema_mapping if isinstance(schema_mapping, Mapping) else build_schema_mapping_report(sample_rows=rows, write=True))
    )
    pit_replay_payload = load_latest_pit_replay()
    quality_exists = _quality_scorecard_path().exists()
    quality_payload = get_latest_managed_data_quality_scorecard() if quality_exists else {}
    sample_fixture_payload = _load_sample_fixture_report()
    sample_fixture_present = bool(sample_fixture_payload.get("sample_data_used"))
    quarantine_snapshot_payload = _load_quarantine_snapshot_report()
    quarantine_snapshot_present = bool(quarantine_snapshot_payload.get("snapshot_pulled"))
    quarantine_contract_payload = _load_quarantine_contract_report()
    research_cache_present = bool(quarantine_contract_payload.get("research_cache_written")) or bool(str(quarantine_contract_payload.get("research_cache_path") or "").strip())
    production_cache_gate_payload = _load_production_cache_gate_report()
    v12_input_contract_payload = _load_v12_input_contract_report()
    missing_ts = _missing_timestamp_fields(rows)
    missing_fund = _missing_fundamental_fields(rows)
    timestamp_coverage = _field_coverage(rows, V12_REQUIRED_TIMESTAMP_FIELDS)
    managed_coverage = _field_coverage(rows, V12_REQUIRED_FUNDAMENTAL_FIELDS)
    local_leakage = _local_leakage_checks(rows)
    audit_leakage = audit_payload.get("leakage_checks") if isinstance(audit_payload.get("leakage_checks"), Mapping) else {}
    leakage_checks = {**local_leakage, **dict(audit_leakage)}

    blocking: list[str] = []
    if not rows:
        blocking.append("managed_rows_missing")
        if sample_fixture_present and not bool(sample_fixture_payload.get("production_eligible")):
            blocking.append("sample_fixture_not_production_data")
        if quarantine_snapshot_present and not bool(quarantine_snapshot_payload.get("production_eligible")):
            blocking.append("quarantine_snapshot_not_production_data")
        if research_cache_present and not bool(quarantine_contract_payload.get("production_eligible")):
            blocking.append("research_cache_not_production_managed_data")
    production_gate_status = str(production_cache_gate_payload.get("status") or "missing").lower()
    if production_gate_status not in {"ready", "pass", "success"}:
        blocking.extend(str(item) for item in (production_cache_gate_payload.get("blocking_reasons") or []))
        blocking.append("production_cache_gate_missing_or_blocked")
    if not bool(production_cache_gate_payload.get("production_cache_write_allowed")):
        blocking.append("production_cache_write_not_allowed")
    if not bool(production_cache_gate_payload.get("production_cache_written")):
        blocking.append("production_cache_not_written")
    if not bool(production_cache_gate_payload.get("feature_store_v12_allowed")):
        blocking.append("production_cache_gate_does_not_allow_v12")
    v12_input_contract_status = str(v12_input_contract_payload.get("status") or "missing").lower()
    if v12_input_contract_status not in {"ready", "pass", "passed", "success", "ok"} or not bool(v12_input_contract_payload.get("input_contract_ready")):
        blocking.extend(str(item) for item in (v12_input_contract_payload.get("blocking_reasons") or []))
        blocking.append("feature_store_v12_input_contract_missing_or_blocked")
    if not bool(schema_mapping_payload.get("schema_mapping_ready")):
        blocking.extend(str(item) for item in (schema_mapping_payload.get("blocking_reasons") or []))
        blocking.append("managed_proxy_schema_mapping_blocked")
    if pit_replay_payload and pit_replay_payload.get("status") != "ready":
        blocking.extend(str(item) for item in (pit_replay_payload.get("blocking_reasons") or []))
        blocking.append("pit_replay_failed")
    quality_warning_reasons: list[str] = []
    if not quality_exists:
        blocking.append("managed_data_quality_missing")
    else:
        quality_warning_reasons = [str(item) for item in (quality_payload.get("warning_reasons") or []) if item]
        if not bool(quality_payload.get("gate_passed")):
            reasons = [str(item) for item in (quality_payload.get("blocking_reasons") or []) if item]
            if reasons:
                blocking.extend(f"managed_data_quality:{reason}" for reason in reasons)
            else:
                blocking.append("managed_data_quality_failed")
    if not health_payload:
        blocking.append("managed_health_missing")
    if not bool(health_payload.get("v12_allowed")):
        blocking.extend(str(item) for item in (health_payload.get("blocking_reasons") or []))
        blocking.append("managed_proxy_health_blocked")
    if not audit_payload or audit_payload.get("status") in {None, ""}:
        blocking.append("managed_audit_missing")
    elif not bool(audit_payload.get("v12_allowed")):
        blocking.extend(str(item) for item in (audit_payload.get("blocking_reasons") or []))
        blocking.append("managed_audit_blocked")
    for field in missing_ts:
        blocking.append(f"missing_{field}")
    if missing_fund:
        blocking.append("managed_fundamental_fields_missing")
    if not bool(leakage_checks.get("source_timestamp_leakage_pass")):
        blocking.append("source_timestamp_leakage")
    if not bool(leakage_checks.get("asof_date_leakage_pass")):
        blocking.append("asof_date_leakage")
    if not bool(leakage_checks.get("feature_date_cutoff_pass")):
        blocking.append("feature_date_cutoff_fail")
    if not bool(leakage_checks.get("ingest_timestamp_not_used_as_asof_pass")):
        blocking.append("ingest_timestamp_cannot_replace_asof_date")
    if not bool(leakage_checks.get("point_in_time_join_ready")):
        blocking.append("point_in_time_join_not_ready")

    blocking = sorted({reason for reason in blocking if reason})
    ready = not blocking
    return sanitize_for_json(
        {
            "status": "ready" if ready else "blocked",
            "ready": ready,
            "v12_allowed": ready,
            "health_status": _health_status(health_payload),
            "audit_status": _audit_status(audit_payload),
            "schema_mapping_status": schema_mapping_payload.get("status", "missing"),
            "schema_mapping_ready": bool(schema_mapping_payload.get("schema_mapping_ready")),
            "pit_replay_status": pit_replay_payload.get("status", "missing") if pit_replay_payload else "missing",
            "pit_replay_ready": bool(pit_replay_payload.get("point_in_time_join_ready")) if pit_replay_payload else False,
            "row_count": len(rows),
            "required_timestamp_fields": list(V12_REQUIRED_TIMESTAMP_FIELDS),
            "missing_timestamp_fields": missing_ts,
            "timestamp_field_coverage": timestamp_coverage,
            "required_fundamental_fields": list(V12_REQUIRED_FUNDAMENTAL_FIELDS),
            "missing_fundamental_fields": missing_fund,
            "managed_field_coverage": managed_coverage,
            "leakage_checks": leakage_checks,
            "point_in_time_join_ready": bool(leakage_checks.get("point_in_time_join_ready")) and not missing_ts,
            "blocking_reasons": blocking,
            "managed_proxy_health": health_payload,
            "managed_audit_readiness": audit_payload,
            "managed_proxy_schema_mapping": schema_mapping_payload,
            "pit_replay_summary": pit_replay_payload,
            "managed_data_quality": quality_payload if quality_exists else {},
            "sample_fixture_contract": sample_fixture_payload,
            "quarantine_snapshot": quarantine_snapshot_payload,
            "quarantine_contract": quarantine_contract_payload,
            "production_cache_gate": production_cache_gate_payload,
            "production_cache_gate_status": production_gate_status,
            "production_cache_written": bool(production_cache_gate_payload.get("production_cache_written")),
            "v12_input_contract": v12_input_contract_payload,
            "v12_input_contract_status": v12_input_contract_status,
            "v12_input_contract_ready": bool(v12_input_contract_payload.get("input_contract_ready")),
            "sample_fixture_used": False,
            "quarantine_snapshot_used": False,
            "research_cache_used": False,
            "sample_data_used": False,
            "production_eligible": False,
            "quality_status": quality_payload.get("status", "missing") if quality_exists else "missing",
            "quality_score": quality_payload.get("quality_score") if quality_exists else None,
            "quality_gate_passed": bool(quality_payload.get("gate_passed")) if quality_exists else False,
            "quality_warning_reasons": quality_warning_reasons,
            "managed_data_used": ready and bool(rows),
            "fake_data_used": False,
            "mock_data_used": False,
            "training_invoked": False,
            "active_updated": False,
            "active_model_written": False,
            "customer_prediction_generated": False,
        }
    )


def _candidate_sort_key(row: Mapping[str, Any]) -> tuple[date, date]:
    return (
        _parse_date(row.get("asof_date")) or date.min,
        _parse_date(row.get("source_timestamp")) or date.min,
    )


def merge_managed_fundamentals_point_in_time(market_frame: pd.DataFrame, managed_rows: Sequence[Mapping[str, Any]]) -> pd.DataFrame:
    frame = market_frame.copy()
    if "prediction_cutoff_date" not in frame.columns:
        frame["prediction_cutoff_date"] = frame.get("trade_date")
    for field in V12_REQUIRED_FUNDAMENTAL_FIELDS:
        frame[field] = pd.NA
    for field in V12_META_FIELDS:
        frame[field] = pd.NA

    rows = [dict(row) for row in managed_rows]
    for idx, sample in frame.iterrows():
        sample_feature = _sample_feature_date(sample)
        cutoff = _sample_cutoff_date(sample)
        if sample_feature is None or cutoff is None:
            continue
        candidates: list[dict[str, Any]] = []
        for row in rows:
            managed_feature = _managed_feature_date(row)
            asof = _parse_date(row.get("asof_date"))
            source = _parse_date(row.get("source_timestamp"))
            if managed_feature != sample_feature:
                continue
            if asof is None or source is None:
                continue
            if asof > cutoff or source > cutoff:
                continue
            candidates.append(row)
        if not candidates:
            continue
        selected = sorted(candidates, key=_candidate_sort_key)[-1]
        for field in V12_REQUIRED_FUNDAMENTAL_FIELDS:
            frame.at[idx, field] = selected.get(field)
        frame.at[idx, "managed_asof_date"] = _date_text(selected.get("asof_date"))
        frame.at[idx, "managed_source_timestamp"] = str(selected.get("source_timestamp") or "")
        frame.at[idx, "managed_ingest_timestamp"] = str(selected.get("ingest_timestamp") or "")
    return frame


def compute_v12_feature_coverage(frame: pd.DataFrame) -> dict[str, Any]:
    rows = frame.to_dict(orient="records") if not frame.empty else []
    managed_coverage = _field_coverage(rows, V12_REQUIRED_FUNDAMENTAL_FIELDS)
    technical_fields = [
        field
        for field in frame.columns
        if field not in set(V12_REQUIRED_FUNDAMENTAL_FIELDS)
        and field not in set(V12_META_FIELDS)
        and field not in {"trade_date", "feature_date", "trading_date", "prediction_cutoff_date"}
        and not str(field).startswith(("ret_", "direction_", "tb_"))
    ]
    technical_rows = frame[technical_fields].to_dict(orient="records") if technical_fields else []
    return {
        "managed_field_coverage": managed_coverage,
        "technical_feature_coverage": _field_coverage(technical_rows, technical_fields),
    }


def validate_v12_no_lookahead(frame: pd.DataFrame) -> dict[str, Any]:
    source_late = 0
    asof_late = 0
    rows_with_join = 0
    for _, row in frame.iterrows():
        cutoff = _sample_cutoff_date(row)
        asof = _parse_date(row.get("managed_asof_date"))
        source = _parse_date(row.get("managed_source_timestamp"))
        if asof or source:
            rows_with_join += 1
        if asof and cutoff and asof > cutoff:
            asof_late += 1
        if source and cutoff and source > cutoff:
            source_late += 1
    return {
        "no_lookahead_pass": source_late == 0 and asof_late == 0,
        "point_in_time_join_ready": rows_with_join > 0 and source_late == 0 and asof_late == 0,
        "joined_row_count": rows_with_join,
        "source_timestamp_late_rows": source_late,
        "asof_date_late_rows": asof_late,
    }


def _date_range(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty or "trade_date" not in frame.columns:
        return {"date_start": None, "date_end": None}
    return {
        "date_start": str(frame["trade_date"].min()),
        "date_end": str(frame["trade_date"].max()),
    }


def build_v12_manifest(
    *,
    status: str,
    readiness: Mapping[str, Any],
    feature_store_path: str | None = None,
    frame: pd.DataFrame | None = None,
    extra_blocking_reasons: Sequence[str] | None = None,
) -> dict[str, Any]:
    manifest_path = _feature_store_manifest_path("v12")
    store_path = feature_store_path or str(_store_path())
    frame = frame if frame is not None else pd.DataFrame()
    coverage = compute_v12_feature_coverage(frame)
    no_lookahead = validate_v12_no_lookahead(frame) if not frame.empty else {"no_lookahead_pass": False, "point_in_time_join_ready": False}
    date_range = _date_range(frame)
    blocking = sorted(set(list(readiness.get("blocking_reasons") or []) + list(extra_blocking_reasons or [])))
    success = status == "success"
    payload = {
        "status": status,
        "version": "v12",
        "feature_store_version": "v12",
        "generated_at": _now(),
        "feature_set": V12_FEATURE_SET,
        "health_status": readiness.get("health_status") or "missing",
        "audit_status": readiness.get("audit_status") or "missing",
        "schema_mapping_status": readiness.get("schema_mapping_status") or "missing",
        "schema_mapping_ready": bool(readiness.get("schema_mapping_ready")),
        "pit_replay_status": readiness.get("pit_replay_status") or "missing",
        "pit_replay_ready": bool(readiness.get("pit_replay_ready")),
        "row_count": int(len(frame)) if success else 0,
        "date_range": date_range,
        "date_start": date_range["date_start"],
        "date_end": date_range["date_end"],
        "required_timestamp_fields": list(V12_REQUIRED_TIMESTAMP_FIELDS),
        "missing_timestamp_fields": readiness.get("missing_timestamp_fields") or [],
        "timestamp_field_coverage": readiness.get("timestamp_field_coverage") or {},
        "required_fundamental_fields": list(V12_REQUIRED_FUNDAMENTAL_FIELDS),
        "missing_fundamental_fields": readiness.get("missing_fundamental_fields") or [],
        "managed_field_coverage": coverage["managed_field_coverage"] if success else readiness.get("managed_field_coverage") or {},
        "technical_feature_coverage": coverage["technical_feature_coverage"],
        "point_in_time_join_ready": bool(no_lookahead.get("point_in_time_join_ready")) if success else bool(readiness.get("point_in_time_join_ready")),
        "no_lookahead_pass": bool(no_lookahead.get("no_lookahead_pass")) if success else False,
        "blocking_reasons": [] if success else blocking,
        "managed_data_used": bool(success and readiness.get("managed_data_used")),
        "fake_data_used": False,
        "mock_data_used": False,
        "sample_data_used": False,
        "baseline_used": False,
        "training_invoked": False,
        "training_dataset_v12_allowed": bool(success and no_lookahead.get("no_lookahead_pass") and no_lookahead.get("point_in_time_join_ready")),
        "active_updated": False,
        "active_model_written": False,
        "customer_prediction_generated": False,
        "manifest_path": str(manifest_path),
        "feature_store_path": store_path,
        "managed_proxy_readiness": {
            "status": "ready" if readiness.get("health_status") == "success_with_required_fields" else "blocked",
            "v12_allowed": bool(readiness.get("managed_proxy_health", {}).get("v12_allowed")),
            "blocking_reasons": readiness.get("managed_proxy_health", {}).get("blocking_reasons") or [],
        },
        "managed_proxy_health": readiness.get("managed_proxy_health") or {},
        "managed_audit_readiness": readiness.get("managed_audit_readiness") or {},
        "managed_proxy_schema_mapping": readiness.get("managed_proxy_schema_mapping") or {},
        "pit_replay_summary": readiness.get("pit_replay_summary") or {},
        "no_fake_data": True,
        "message_zh": "Feature Store v12 built with point-in-time managed fundamentals."
        if success
        else "Feature Store v12 blocked until managed proxy health and PIT audit both pass.",
    }
    return _write_json(manifest_path, payload)


def build_feature_store_v12() -> dict[str, Any]:
    managed_rows = _load_managed_rows()
    readiness = validate_v12_managed_readiness(managed_rows=managed_rows)
    if not readiness["v12_allowed"]:
        return build_v12_manifest(status="blocked", readiness=readiness)

    base = build_feature_store_v10()
    source_path = Path(str(base.get("feature_store_path") or ""))
    if not source_path.is_file():
        blocked = dict(readiness)
        blocked["blocking_reasons"] = sorted(set(list(blocked.get("blocking_reasons") or []) + ["base_feature_store_missing"]))
        return build_v12_manifest(status="blocked", readiness=blocked)

    try:
        base_frame = pd.read_csv(source_path)
    except Exception:
        blocked = dict(readiness)
        blocked["blocking_reasons"] = sorted(set(list(blocked.get("blocking_reasons") or []) + ["base_feature_store_unreadable"]))
        return build_v12_manifest(status="blocked", readiness=blocked)

    merged = merge_managed_fundamentals_point_in_time(base_frame, managed_rows)
    no_lookahead = validate_v12_no_lookahead(merged)
    if not bool(no_lookahead.get("no_lookahead_pass")) or not bool(no_lookahead.get("point_in_time_join_ready")):
        blocked = dict(readiness)
        reasons = list(blocked.get("blocking_reasons") or [])
        if not bool(no_lookahead.get("no_lookahead_pass")):
            reasons.append("v12_no_lookahead_failed")
        if not bool(no_lookahead.get("point_in_time_join_ready")):
            reasons.append("v12_point_in_time_join_not_ready")
        blocked["blocking_reasons"] = sorted(set(reasons))
        return build_v12_manifest(status="blocked", readiness=blocked, frame=merged)

    store_path = _write_store_frame(merged, "v12")
    return build_v12_manifest(status="success", readiness=readiness, feature_store_path=store_path, frame=merged)


def get_feature_store_v12_status() -> dict[str, Any]:
    manifest_path = _feature_store_manifest_path("v12")
    payload = _read_json(manifest_path)
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return sanitize_for_json(
        {
            "status": "not_built",
            "version": "v12",
            "feature_store_version": "v12",
            "manifest_path": str(manifest_path),
            "feature_store_path": str(_store_path()),
            "health_status": "missing",
            "audit_status": "missing",
            "required_timestamp_fields": list(V12_REQUIRED_TIMESTAMP_FIELDS),
            "required_fundamental_fields": list(V12_REQUIRED_FUNDAMENTAL_FIELDS),
            "blocking_reasons": ["feature_store_v12_not_built"],
            "managed_data_used": False,
            "fake_data_used": False,
            "mock_data_used": False,
            "training_invoked": False,
            "training_dataset_v12_allowed": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )
