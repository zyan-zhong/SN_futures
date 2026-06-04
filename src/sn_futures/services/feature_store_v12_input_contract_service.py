from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .feature_store_v12_service import V12_REQUIRED_FUNDAMENTAL_FIELDS, V12_REQUIRED_TIMESTAMP_FIELDS, build_feature_store_v12


CONTRACT_VERSION = "feature_store_v12_input_contract_v1"
CONTRACT_REPORT_FILENAME = "feature_store_v12_input_contract_report.json"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _diagnostics_path(filename: str) -> Path:
    return _output_dir() / "diagnostics" / filename


def _production_cache_path() -> Path:
    return _output_dir() / "fundamentals" / "managed_fundamentals.json"


def _report_path() -> Path:
    path = _diagnostics_path(CONTRACT_REPORT_FILENAME)
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
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


def _status(payload: Any) -> str:
    if not isinstance(payload, Mapping):
        return "missing"
    return str(payload.get("status") or "missing").lower()


def _ready(payload: Any) -> bool:
    return _status(payload) in {"ready", "pass", "passed", "success", "ok"}


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("rows") or payload.get("data") or payload.get("history") or []
    else:
        rows = payload
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _present(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def _parse_date(value: Any) -> date | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
    except Exception:
        pass
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            sample = text[:10] if fmt == "%Y-%m-%d" else text[:8]
            return datetime.strptime(sample, fmt).date()
        except Exception:
            continue
    return None


def _date_range(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = sorted(
        {
            parsed.isoformat()
            for row in rows
            for parsed in [_parse_date(row.get("feature_date") or row.get("trading_date") or row.get("date"))]
            if parsed is not None
        }
    )
    return {"date_start": values[0] if values else "", "date_end": values[-1] if values else "", "row_count": len(rows)}


def _days_between(start: Any, end: Any) -> int:
    start_dt = _parse_date(start)
    end_dt = _parse_date(end)
    if start_dt is None or end_dt is None or end_dt < start_dt:
        return 0
    return (end_dt - start_dt).days + 1


def _field_coverage(rows: Sequence[Mapping[str, Any]], fields: Sequence[str]) -> dict[str, Any]:
    row_count = len(rows)
    by_field: dict[str, Any] = {}
    for field in fields:
        if field == "feature_date":
            present = sum(1 for row in rows if _present(row.get("feature_date") or row.get("trading_date")))
        else:
            present = sum(1 for row in rows if _present(row.get(field)))
        missing = max(row_count - present, 0)
        by_field[field] = {
            "present": present,
            "missing": missing,
            "coverage": round(present / row_count, 4) if row_count else 0.0,
            "missing_rate": round(missing / row_count, 4) if row_count else 1.0,
        }
    complete_rows = sum(1 for row in rows if all(_present(row.get(field)) for field in fields))
    return {
        "row_count": row_count,
        "complete_rows": complete_rows,
        "complete_ratio": round(complete_rows / row_count, 4) if row_count else 0.0,
        "by_field": by_field,
    }


def _timestamp_coverage(rows: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    row_count = len(rows)
    by_field: dict[str, Any] = {}
    for field in V12_REQUIRED_TIMESTAMP_FIELDS:
        if field == "feature_date":
            present = sum(1 for row in rows if _present(row.get("feature_date") or row.get("trading_date")))
        else:
            present = sum(1 for row in rows if _present(row.get(field)))
        missing = max(row_count - present, 0)
        by_field[field] = {
            "present": present,
            "missing": missing,
            "coverage": round(present / row_count, 4) if row_count else 0.0,
            "missing_rate": round(missing / row_count, 4) if row_count else 1.0,
        }
    complete_rows = 0
    for row in rows:
        if all(_present(row.get(field)) if field != "feature_date" else _present(row.get("feature_date") or row.get("trading_date")) for field in V12_REQUIRED_TIMESTAMP_FIELDS):
            complete_rows += 1
    return {
        "row_count": row_count,
        "complete_rows": complete_rows,
        "complete_ratio": round(complete_rows / row_count, 4) if row_count else 0.0,
        "by_field": by_field,
    }


def validate_v12_input_contract_no_lookahead(rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    rows = list(rows if rows is not None else _rows_from_payload(_read_json(_production_cache_path())))
    source_late = 0
    asof_late = 0
    feature_late = 0
    for row in rows:
        cutoff = _parse_date(row.get("prediction_cutoff_date"))
        source = _parse_date(row.get("source_timestamp"))
        asof = _parse_date(row.get("asof_date"))
        feature_date = _parse_date(row.get("feature_date") or row.get("trading_date"))
        if cutoff and source and source > cutoff:
            source_late += 1
        if cutoff and asof and asof > cutoff:
            asof_late += 1
        if cutoff and feature_date and feature_date > cutoff:
            feature_late += 1
    blocking = []
    if source_late:
        blocking.append("source_timestamp_leakage")
    if asof_late:
        blocking.append("asof_date_leakage")
    if feature_late:
        blocking.append("feature_date_cutoff_fail")
    return sanitize_for_json(
        {
            "status": "pass" if not blocking and rows else "fail",
            "source_timestamp_leakage_rows": source_late,
            "asof_date_leakage_rows": asof_late,
            "feature_date_cutoff_fail_rows": feature_late,
            "point_in_time_join_ready": bool(rows) and not blocking,
            "blocking_reasons": blocking or ([] if rows else ["production_cache_missing"]),
        }
    )


def _load_backfill_budget() -> tuple[dict[str, Any], dict[str, Any]]:
    planner = _read_json(_diagnostics_path("managed_data_backfill_planner_report.json"))
    if not isinstance(planner, Mapping):
        return {}, {"date_start": "", "date_end": ""}
    return (
        dict(planner.get("coverage_budget") or {}) if isinstance(planner.get("coverage_budget"), Mapping) else {},
        dict(planner.get("required_date_range") or {}) if isinstance(planner.get("required_date_range"), Mapping) else {"date_start": "", "date_end": ""},
    )


def compute_v12_input_readiness_diff(rows: Sequence[Mapping[str, Any]] | None = None) -> dict[str, Any]:
    rows = list(rows if rows is not None else _rows_from_payload(_read_json(_production_cache_path())))
    budget, required_range = _load_backfill_budget()
    available_range = _date_range(rows)
    field_cov = _field_coverage(rows, V12_REQUIRED_FUNDAMENTAL_FIELDS)
    timestamp_cov = _timestamp_coverage(rows)
    required_days = _days_between(required_range.get("date_start"), required_range.get("date_end"))
    available_days = _days_between(available_range.get("date_start"), available_range.get("date_end"))
    date_ratio = round(available_days / required_days, 4) if required_days else 0.0
    min_rows = int(budget.get("min_row_count") or 0)
    max_missing = budget.get("max_missing_rate_by_required_field") if isinstance(budget.get("max_missing_rate_by_required_field"), Mapping) else {}
    field_failures: list[str] = []
    for field, stats in field_cov["by_field"].items():
        limit = float(max_missing.get(field, 1.0))
        if float(stats.get("missing_rate") or 0.0) > limit:
            field_failures.append(str(field))
    coverage_blocking = []
    if len(rows) < min_rows:
        coverage_blocking.append("row_count_below_budget")
    if date_ratio < float(budget.get("min_date_coverage_ratio") or 0.0):
        coverage_blocking.append("date_coverage_below_budget")
    if field_failures:
        coverage_blocking.append("coverage_below_budget")
    if float(timestamp_cov.get("complete_ratio") or 0.0) < float(budget.get("min_timestamp_coverage") or 0.0):
        coverage_blocking.append("timestamp_coverage_below_budget")
    return sanitize_for_json(
        {
            "row_count": len(rows),
            "min_row_count": min_rows,
            "date_coverage_ratio": date_ratio,
            "min_date_coverage_ratio": budget.get("min_date_coverage_ratio", 0),
            "timestamp_complete_ratio": timestamp_cov.get("complete_ratio", 0),
            "min_timestamp_coverage": budget.get("min_timestamp_coverage", 0),
            "field_coverage": field_cov,
            "timestamp_coverage": timestamp_cov,
            "field_failures": field_failures,
            "blocking_reasons": coverage_blocking,
        }
    )


def compare_production_cache_against_v12_requirements() -> dict[str, Any]:
    cache_payload = _read_json(_production_cache_path())
    rows = _rows_from_payload(cache_payload)
    gate = _read_json(_diagnostics_path("managed_data_production_cache_gate_report.json"))
    pit_replay = _read_json(_diagnostics_path("managed_pit_replay_report.json"))
    audit = _read_json(_diagnostics_path("managed_data_audit_manifest.json"))
    quality = _read_json(_diagnostics_path("managed_data_quality_scorecard.json"))
    budget, required_range = _load_backfill_budget()
    available_range = _date_range(rows)
    coverage_diff = compute_v12_input_readiness_diff(rows)
    no_lookahead = validate_v12_input_contract_no_lookahead(rows)

    missing_required = [field for field in V12_REQUIRED_FUNDAMENTAL_FIELDS if not rows or not any(_present(row.get(field)) for row in rows)]
    missing_timestamps: list[str] = []
    for field in V12_REQUIRED_TIMESTAMP_FIELDS:
        if field == "feature_date":
            if not rows or any(not _present(row.get("feature_date") or row.get("trading_date")) for row in rows):
                missing_timestamps.append(field)
        elif not rows or any(not _present(row.get(field)) for row in rows):
            missing_timestamps.append(field)

    pit_replay_pass = bool(isinstance(pit_replay, Mapping) and _ready(pit_replay) and pit_replay.get("point_in_time_join_ready"))
    audit_leakage = audit.get("leakage_checks") if isinstance(audit, Mapping) and isinstance(audit.get("leakage_checks"), Mapping) else {}
    audit_pass = bool(isinstance(audit, Mapping) and _ready(audit) and audit.get("v12_allowed"))
    quality_score = float(quality.get("quality_score") or 0.0) if isinstance(quality, Mapping) else 0.0
    quality_pass = bool(
        isinstance(quality, Mapping)
        and _ready(quality)
        and quality.get("gate_passed")
        and quality_score >= float(budget.get("min_quality_score") or 0.0)
    )
    required_days = _days_between(required_range.get("date_start"), required_range.get("date_end"))
    available_days = _days_between(available_range.get("date_start"), available_range.get("date_end"))
    date_ok = bool(required_days and available_days >= required_days and str(available_range.get("date_start")) <= str(required_range.get("date_start")) and str(available_range.get("date_end")) >= str(required_range.get("date_end")))

    blocking: list[str] = []
    if not rows:
        blocking.append("production_cache_missing")
    if not (isinstance(gate, Mapping) and _ready(gate) and gate.get("production_cache_written")):
        blocking.append("production_cache_gate_blocked")
    if missing_required:
        blocking.append("missing_required_fields")
    if missing_timestamps:
        blocking.append("missing_timestamp_fields")
    if required_range and not date_ok:
        blocking.append("date_range_insufficient")
    blocking.extend(str(item) for item in coverage_diff.get("blocking_reasons") or [])
    if coverage_diff.get("field_failures"):
        blocking.append("coverage_below_budget")
    if not pit_replay_pass:
        blocking.append("pit_replay_not_passed")
    if not audit_pass:
        blocking.append("pit_audit_not_passed")
    if not quality_pass:
        blocking.append("data_quality_not_passed")
    if no_lookahead.get("status") != "pass":
        blocking.append("no_lookahead_not_passed")
    blocking = sorted({reason for reason in blocking if reason})
    ready = not blocking
    return sanitize_for_json(
        {
            "status": "ready" if ready else "blocked",
            "production_cache_path": str(_production_cache_path()),
            "required_fields": list(V12_REQUIRED_FUNDAMENTAL_FIELDS),
            "missing_required_fields": missing_required,
            "required_timestamp_fields": list(V12_REQUIRED_TIMESTAMP_FIELDS),
            "missing_timestamp_fields": missing_timestamps,
            "date_range_required": required_range,
            "date_range_available": available_range,
            "coverage_diff": coverage_diff,
            "pit_readiness": {
                "pit_replay_status": pit_replay.get("status", "missing") if isinstance(pit_replay, Mapping) else "missing",
                "pit_replay_pass": pit_replay_pass,
                "pit_audit_status": audit.get("status", "missing") if isinstance(audit, Mapping) else "missing",
                "pit_audit_pass": audit_pass,
                "leakage_checks": audit_leakage,
            },
            "quality_readiness": {
                "status": quality.get("status", "missing") if isinstance(quality, Mapping) else "missing",
                "gate_passed": bool(quality.get("gate_passed")) if isinstance(quality, Mapping) else False,
                "quality_score": quality_score,
                "min_quality_score": budget.get("min_quality_score", 0),
            },
            "no_lookahead_readiness": no_lookahead,
            "input_contract_ready": ready,
            "blocking_reasons": blocking,
        }
    )


def build_v12_input_contract() -> dict[str, Any]:
    diff = compare_production_cache_against_v12_requirements()
    ready = bool(diff.get("input_contract_ready"))
    return sanitize_for_json(
        {
            "status": "ready" if ready else "blocked",
            "generated_at": _now(),
            "contract_version": CONTRACT_VERSION,
            **{key: diff[key] for key in (
                "production_cache_path",
                "required_fields",
                "missing_required_fields",
                "required_timestamp_fields",
                "missing_timestamp_fields",
                "date_range_required",
                "date_range_available",
                "coverage_diff",
                "pit_readiness",
                "quality_readiness",
                "no_lookahead_readiness",
                "input_contract_ready",
                "blocking_reasons",
            )},
            "feature_store_v12_build_allowed": False,
            "warning_reasons": ["input contract is necessary but does not automatically build Feature Store v12"],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
            "report_path": str(_report_path()),
        }
    )


def build_v12_input_contract_report() -> dict[str, Any]:
    return _write_json(_report_path(), build_v12_input_contract())


def get_latest_v12_input_contract_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    report = build_v12_input_contract()
    report["blocking_reasons"] = sorted(set(list(report.get("blocking_reasons") or []) + ["v12_input_contract_report_missing"]))
    report["status"] = "blocked"
    report["input_contract_ready"] = False
    return sanitize_for_json(report)
