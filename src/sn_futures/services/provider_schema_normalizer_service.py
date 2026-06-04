from __future__ import annotations

from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..utils.secret_sanitizer import sanitize_mapping


CANONICAL_PROVIDER_FIELDS = (
    "symbol",
    "close",
    "source_timestamp",
    "asof_date",
    "ingest_timestamp",
    "freshness",
)


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _as_rows(value: Any) -> list[Mapping[str, Any]]:
    if isinstance(value, list):
        return [row for row in value if isinstance(row, Mapping)]
    return []


def normalize_provider_sample(provider_id: str, payload: Mapping[str, Any] | None) -> dict[str, Any]:
    source = dict(payload or {})
    rows = _as_rows(source.get("rows"))
    fields_seen: list[str] = []
    raw_fields = source.get("fields")
    if isinstance(raw_fields, list):
        fields_seen.extend(str(field) for field in raw_fields if str(field or "").strip())
    for row in rows:
        fields_seen.extend(str(key) for key in row.keys())
    fields_seen = sorted(set(fields_seen))
    canonical_seen = [field for field in CANONICAL_PROVIDER_FIELDS if field in fields_seen]
    return _safe(
        {
            "provider": provider_id,
            "row_count": len(rows),
            "fields_seen": fields_seen,
            "canonical_fields_seen": canonical_seen,
            "missing_canonical_fields": [field for field in CANONICAL_PROVIDER_FIELDS if field not in fields_seen],
            "freshness_status": str(source.get("freshness") or "unknown"),
            "field_coverage_ratio": round(len(canonical_seen) / len(CANONICAL_PROVIDER_FIELDS), 4),
        }
    )
