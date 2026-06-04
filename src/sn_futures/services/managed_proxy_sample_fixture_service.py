from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import contains_secret_like_value
from .managed_data_audit_service import validate_managed_point_in_time_rows
from .managed_data_quality_service import build_managed_data_quality_scorecard
from .managed_pit_replay_service import build_pit_replay_report
from .managed_proxy_schema_mapper_service import CANONICAL_FIELDS, build_schema_mapping_report


FIXTURE_VERSION = "managed_proxy_sample_fixture_v1"
FIXTURE_REPORT_FILENAME = "managed_proxy_sample_fixture_contract_report.json"
DEFAULT_FIXTURE_PATH = Path("config") / "managed_proxy.sample_fixture.example.json"
SENSITIVE_KEY_HINTS = ("authorization", "token", "secret", "password", "api_key", "apikey", "header")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / FIXTURE_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _resolve_fixture_path(fixture_path: str | Path | None) -> Path:
    if fixture_path is None:
        return _project_root() / DEFAULT_FIXTURE_PATH
    path = Path(fixture_path)
    return path if path.is_absolute() else _project_root() / path


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return None


def _write_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path = _report_path()
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    rows = payload.get("rows") or payload.get("data") or payload.get("history") if isinstance(payload, Mapping) else payload
    if not isinstance(rows, list):
        return []
    return [dict(row) for row in rows if isinstance(row, Mapping)]


def _secret_like_key_or_value(payload: Any) -> bool:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            lower = str(key).lower()
            if any(hint in lower for hint in SENSITIVE_KEY_HINTS):
                return True
            if _secret_like_key_or_value(value):
                return True
        return False
    if isinstance(payload, list):
        return any(_secret_like_key_or_value(item) for item in payload)
    if isinstance(payload, str):
        return contains_secret_like_value(payload)
    return False


def _base_payload(*, fixture_path: Path | None = None) -> dict[str, Any]:
    return {
        "status": "blocked",
        "generated_at": _now(),
        "fixture_version": FIXTURE_VERSION,
        "fixture_path": str(fixture_path) if fixture_path else "",
        "row_count": 0,
        "schema_contract_status": "not_run",
        "pit_replay_status": "not_run",
        "data_quality_status": "not_run",
        "sample_data_used": True,
        "managed_data_used": False,
        "fake_data_used": False,
        "mock_data_used": False,
        "production_eligible": False,
        "feature_store_v12_allowed": False,
        "blocking_reasons": [],
        "warning_reasons": [],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }


def validate_sample_fixture_file(fixture_path: str | Path | None = None) -> dict[str, Any]:
    path = _resolve_fixture_path(fixture_path)
    payload = _base_payload(fixture_path=path)
    blocking: list[str] = []
    raw = _read_json(path)
    if raw is None:
        blocking.append("fixture_file_missing")
    elif not isinstance(raw, Mapping):
        blocking.append("fixture_payload_invalid")
    else:
        if raw.get("fixture_only") is not True:
            blocking.append("fixture_only_marker_missing")
        if _secret_like_key_or_value(raw):
            blocking.append("fixture_secret_like_value_detected")
        rows = _rows_from_payload(raw)
        if not rows:
            blocking.append("fixture_rows_missing")
        payload["row_count"] = len(rows)

    payload["status"] = "accepted" if not blocking else "rejected"
    payload["blocking_reasons"] = sorted(set(blocking))
    return sanitize_for_json(payload)


def _load_fixture_rows(path: Path) -> list[dict[str, Any]]:
    raw = _read_json(path)
    if not isinstance(raw, Mapping):
        return []
    return _rows_from_payload(raw)


def _contract_status(report: Mapping[str, Any], ready_key: str | None = None) -> str:
    if ready_key:
        return "ready" if bool(report.get(ready_key)) else "blocked"
    return str(report.get("status") or "blocked")


def _quality_status(report: Mapping[str, Any]) -> str:
    return "pass" if bool(report.get("gate_passed")) else "blocked"


def _missing_required_fields_by_row(rows: Sequence[Mapping[str, Any]]) -> list[str]:
    missing: set[str] = set()
    if not rows:
        return list(CANONICAL_FIELDS)
    for row in rows:
        for field in CANONICAL_FIELDS:
            if field == "feature_date":
                value = row.get("feature_date") or row.get("trading_date")
            else:
                value = row.get(field)
            if value is None or str(value).strip() == "":
                missing.add(str(field))
    return sorted(missing)


def _prefixed_reasons(prefix: str, reasons: Sequence[Any]) -> list[str]:
    return [f"{prefix}:{reason}" for reason in reasons if str(reason or "").strip()]


def build_sample_fixture_contract_report(
    *,
    fixture_path: str | Path | None = None,
    rows: Sequence[Mapping[str, Any]] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    path = _resolve_fixture_path(fixture_path)
    validation = validate_sample_fixture_file(path)
    fixture_rows = [dict(row) for row in rows] if rows is not None else _load_fixture_rows(path)
    report = _base_payload(fixture_path=path)
    report["row_count"] = len(fixture_rows)

    blocking: list[str] = list(validation.get("blocking_reasons") or [])
    warnings: list[str] = []
    if validation.get("status") == "rejected":
        report["blocking_reasons"] = sorted(set(blocking))
        return _write_report(report) if write else sanitize_for_json(report)

    schema = build_schema_mapping_report(sample_rows=fixture_rows, field_mapping={}, write=False)
    pit_replay = build_pit_replay_report(rows=fixture_rows, write=False)
    pit_audit = validate_managed_point_in_time_rows(fixture_rows)
    quality = build_managed_data_quality_scorecard(rows=fixture_rows, write=False)
    row_missing_fields = _missing_required_fields_by_row(fixture_rows)

    schema_status = _contract_status(schema, "schema_mapping_ready")
    if row_missing_fields:
        schema_status = "blocked"
    pit_status = _contract_status(pit_replay, "point_in_time_join_ready")
    quality_status = _quality_status(quality)
    report.update(
        {
            "schema_contract_status": schema_status,
            "pit_replay_status": pit_status,
            "data_quality_status": quality_status,
            "schema_contract_summary": {
                "mapped_fields_count": len(schema.get("mapped_fields") or []),
                "unmapped_required_fields": schema.get("unmapped_required_fields") or [],
            },
            "pit_replay_summary": {
                "cases_run": pit_replay.get("cases_run", 0),
                "cases_passed": pit_replay.get("cases_passed", 0),
                "cases_failed": pit_replay.get("cases_failed", 0),
                "point_in_time_join_ready": bool(pit_replay.get("point_in_time_join_ready")),
            },
            "data_quality_summary": {
                "quality_score": quality.get("quality_score"),
                "gate_passed": bool(quality.get("gate_passed")),
                "duplicate_key_count": quality.get("duplicate_key_count", 0),
                "invalid_value_count": quality.get("invalid_value_count", 0),
            },
        }
    )

    if schema_status != "ready":
        blocking.extend(str(item) for item in (schema.get("blocking_reasons") or []))
        if row_missing_fields:
            blocking.append("canonical_required_fields_missing")
    if pit_status != "ready":
        blocking.extend(str(item) for item in (pit_replay.get("blocking_reasons") or []))
    if pit_audit.get("status") != "pass":
        blocking.extend(str(item) for item in (pit_audit.get("blocking_reasons") or []))
    if quality_status != "pass":
        blocking.extend(_prefixed_reasons("managed_data_quality", quality.get("blocking_reasons") or []))
    warnings.extend(str(item) for item in (quality.get("warning_reasons") or []) if item)

    blocking = sorted({reason for reason in blocking if reason})
    report["status"] = "ready" if not blocking else "blocked"
    report["blocking_reasons"] = blocking
    report["warning_reasons"] = sorted({warning for warning in warnings if warning})
    return _write_report(report) if write else sanitize_for_json(report)


def import_managed_proxy_sample_fixture(fixture_path: str | Path | None = None) -> dict[str, Any]:
    return build_sample_fixture_contract_report(fixture_path=fixture_path, write=True)


def run_fixture_contract_tests(fixture_path: str | Path | None = None) -> dict[str, Any]:
    return build_sample_fixture_contract_report(fixture_path=fixture_path, write=True)


def get_latest_sample_fixture_report() -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            return sanitize_for_json(dict(payload))
    report = _base_payload()
    report["blocking_reasons"] = ["sample_fixture_report_missing"]
    return sanitize_for_json(report)
