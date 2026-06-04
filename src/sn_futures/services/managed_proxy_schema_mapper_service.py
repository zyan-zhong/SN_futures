from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..user_data import secrets_path
from .managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS


MAPPING_VERSION = "managed_proxy_schema_mapping_v1"
MAPPING_REPORT_FILENAME = "managed_proxy_schema_mapping_report.json"
FEATURE_DATE_CANONICAL_ALIASES = ("feature_date", "trading_date")
REQUIRED_TIMESTAMP_FIELDS = (
    "source_timestamp",
    "asof_date",
    "ingest_timestamp",
    "feature_date",
    "prediction_cutoff_date",
)
REQUIRED_FUNDAMENTAL_FIELDS = tuple(MANAGED_REQUIRED_RESEARCH_FIELDS)
CANONICAL_FIELDS = tuple(
    dict.fromkeys(
        [
            "source_timestamp",
            "asof_date",
            "ingest_timestamp",
            "feature_date",
            "prediction_cutoff_date",
            *REQUIRED_FUNDAMENTAL_FIELDS,
        ]
    )
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _report_path() -> Path:
    path = get_user_output_dir() / "diagnostics" / MAPPING_REPORT_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _write_report(payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path = _report_path()
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _normalise_mapping(payload: Mapping[str, Any]) -> dict[str, Any]:
    raw = payload.get("field_mapping") if isinstance(payload.get("field_mapping"), Mapping) else payload
    return {str(provider): value for provider, value in dict(raw).items() if str(provider).strip()}


def load_managed_proxy_field_mapping(*, project_root: Path | None = None) -> dict[str, str]:
    root = project_root or _project_root()
    candidates = [
        root / "config" / "managed_proxy.mapping.local.json",
        secrets_path().parent / "managed_proxy.mapping.local.json",
    ]
    for path in candidates:
        payload = _read_json(path)
        if not payload:
            continue
        mapping = _normalise_mapping(payload)
        return {key: str(value) for key, value in mapping.items() if isinstance(value, str)}
    return {}


def _provider_fields(rows: list[Mapping[str, Any]]) -> list[str]:
    fields: set[str] = set()
    for row in rows:
        fields.update(str(key) for key in row.keys())
    return sorted(fields)


def detect_ambiguous_field_mapping(field_mapping: Mapping[str, Any]) -> list[dict[str, Any]]:
    ambiguous: list[dict[str, Any]] = []
    for provider, target in field_mapping.items():
        if isinstance(target, (list, tuple, set)):
            targets = [str(item) for item in target if str(item).strip()]
            if len(targets) > 1:
                ambiguous.append({"provider_field": str(provider), "canonical_fields": targets})
    return ambiguous


def _duplicate_targets(field_mapping: Mapping[str, Any]) -> list[dict[str, Any]]:
    target_to_provider: dict[str, list[str]] = {}
    for provider, target in field_mapping.items():
        if not isinstance(target, str):
            continue
        target_to_provider.setdefault(target, []).append(str(provider))
    return [
        {"canonical_field": target, "provider_fields": providers}
        for target, providers in sorted(target_to_provider.items())
        if len(providers) > 1
    ]


def apply_field_mapping_to_sample_rows(rows: list[Mapping[str, Any]], field_mapping: Mapping[str, str]) -> list[dict[str, Any]]:
    mapped_rows: list[dict[str, Any]] = []
    for row in rows:
        mapped = dict(row)
        for provider, canonical in field_mapping.items():
            if provider in row and canonical:
                mapped[str(canonical)] = row[provider]
        mapped_rows.append(mapped)
    return mapped_rows


def _missing_canonical_fields(rows: list[Mapping[str, Any]]) -> list[str]:
    if not rows:
        return list(CANONICAL_FIELDS)
    missing: list[str] = []
    for field in CANONICAL_FIELDS:
        if field == "feature_date":
            present = any(
                row.get("feature_date") not in {None, ""} or row.get("trading_date") not in {None, ""}
                for row in rows
            )
        else:
            present = any(row.get(field) not in {None, ""} for row in rows)
        if not present:
            missing.append(field)
    return missing


def detect_missing_canonical_fields(rows: list[Mapping[str, Any]], field_mapping: Mapping[str, str] | None = None) -> list[str]:
    mapped = apply_field_mapping_to_sample_rows(rows, field_mapping or {})
    return _missing_canonical_fields(mapped)


def validate_field_mapping_contract(
    *,
    sample_rows: list[Mapping[str, Any]] | None = None,
    field_mapping: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    rows = [dict(row) for row in (sample_rows or []) if isinstance(row, Mapping)]
    mapping = dict(field_mapping or {})
    provider_fields = _provider_fields(rows)
    ambiguous = detect_ambiguous_field_mapping(mapping)
    duplicate_targets = _duplicate_targets(mapping)
    missing_provider_fields = [
        str(provider)
        for provider, target in mapping.items()
        if isinstance(target, str) and rows and provider not in provider_fields
    ]
    clean_mapping = {str(provider): str(target) for provider, target in mapping.items() if isinstance(target, str)}
    mapped_rows = apply_field_mapping_to_sample_rows(rows, clean_mapping)
    unmapped_required = _missing_canonical_fields(mapped_rows)
    missing_ts = [field for field in REQUIRED_TIMESTAMP_FIELDS if field in unmapped_required]
    blocking: list[str] = []
    if ambiguous:
        blocking.append("ambiguous_field_mapping")
    if duplicate_targets:
        blocking.append("duplicate_canonical_targets")
    if missing_provider_fields:
        blocking.append("mapping_provider_field_missing")
    if missing_ts:
        blocking.append("canonical_timestamp_fields_missing")
    if unmapped_required:
        blocking.append("canonical_required_fields_missing")
    return {
        "provider_fields_seen": provider_fields,
        "mapped_fields": sorted(set(clean_mapping.values())),
        "unmapped_required_fields": unmapped_required,
        "ambiguous_mappings": ambiguous,
        "duplicate_targets": duplicate_targets,
        "missing_provider_fields": sorted(missing_provider_fields),
        "timestamp_mapping_status": "pass" if not missing_ts else "blocked",
        "schema_mapping_ready": not blocking,
        "blocking_reasons": list(dict.fromkeys(blocking)),
        "mapped_rows": mapped_rows,
    }


def build_schema_mapping_report(
    *,
    sample_rows: list[Mapping[str, Any]] | None = None,
    field_mapping: Mapping[str, Any] | None = None,
    project_root: Path | None = None,
    write: bool = True,
) -> dict[str, Any]:
    mapping = dict(field_mapping) if field_mapping is not None else load_managed_proxy_field_mapping(project_root=project_root)
    contract = validate_field_mapping_contract(sample_rows=sample_rows or [], field_mapping=mapping)
    status = "ready" if contract["schema_mapping_ready"] else "blocked"
    payload = {
        "status": status,
        "mapping_version": MAPPING_VERSION,
        "generated_at": _now(),
        "canonical_fields": list(CANONICAL_FIELDS),
        "provider_fields_seen": contract["provider_fields_seen"],
        "mapped_fields": contract["mapped_fields"],
        "mapping_applied": bool(mapping),
        "unmapped_required_fields": contract["unmapped_required_fields"],
        "ambiguous_mappings": contract["ambiguous_mappings"],
        "duplicate_targets": contract["duplicate_targets"],
        "missing_provider_fields": contract["missing_provider_fields"],
        "timestamp_mapping_status": contract["timestamp_mapping_status"],
        "schema_mapping_ready": bool(contract["schema_mapping_ready"]),
        "blocking_reasons": contract["blocking_reasons"],
        "warning_reasons": [] if status == "ready" else ["managed proxy schema mapping must pass before v12 readiness."],
        "fake_data_used": False,
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "report_path": str(_report_path()),
    }
    return _write_report(payload) if write else sanitize_for_json(payload)


def refresh_schema_mapping_report(
    *,
    sample_rows: list[Mapping[str, Any]] | None = None,
    field_mapping: Mapping[str, Any] | None = None,
    project_root: Path | None = None,
) -> dict[str, Any]:
    return build_schema_mapping_report(sample_rows=sample_rows, field_mapping=field_mapping, project_root=project_root, write=True)


def get_schema_mapping_report() -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                return sanitize_for_json(dict(payload))
        except Exception:
            pass
    return build_schema_mapping_report(sample_rows=[], write=True)
