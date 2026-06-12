from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .stores import atomic_write_json, content_hash, data_layer_root, read_json, safe_payload, utc_now, validate_no_sample


WATERMARK_SCHEMA_VERSION = "data-layer-watermark-v1"


def _clean_status(value: Any, default: str) -> str:
    text = str(value or default).strip().lower()
    return text or default


def _allowed_downstream(record: Mapping[str, Any], status: str) -> bool:
    if status != "ready":
        return False
    if bool(record.get("latest_quote_display_only") or record.get("display_only")):
        return False
    return str(record.get("data_kind") or "").strip().lower() == "daily_bar"


def _normalize_record(record: Mapping[str, Any]) -> dict[str, Any]:
    row_count = int(record.get("row_count") or 0)
    cache_status = _clean_status(record.get("cache_status"), "remote" if row_count else "missing")
    stale_status = _clean_status(record.get("stale_status"), "fresh" if row_count else "missing")
    status = "ready"
    blocking_reasons: list[str] = [
        str(reason)
        for reason in (record.get("blocking_reasons") if isinstance(record.get("blocking_reasons"), list) else [])
        if str(reason or "").strip()
    ]
    data_kind = str(record.get("data_kind") or "unknown")
    if row_count <= 0 or cache_status == "missing":
        status = "missing"
        blocking_reasons.append(f"{data_kind}:missing")
    elif stale_status == "stale":
        status = "stale"
        blocking_reasons.append(f"{data_kind}:stale")
    elif stale_status == "missing":
        status = "missing"
        blocking_reasons.append(f"{data_kind}:missing")
    payload = {
        "provider_id": str(record.get("provider_id") or "unknown_provider"),
        "data_kind": data_kind,
        "row_count": row_count,
        "fetched_at": str(record.get("fetched_at") or ""),
        "source_published_at": str(record.get("source_published_at") or record.get("source_timestamp") or ""),
        "source_timestamp": str(record.get("source_timestamp") or record.get("source_published_at") or ""),
        "cache_status": cache_status,
        "stale_status": stale_status,
        "content_hash": str(record.get("content_hash") or content_hash(dict(record))),
        "status": status,
        "sample_data_used": False,
        "baseline_used": False,
        "fake_data_used": False,
        "demo_data_used": False,
        "latest_quote_display_only": bool(record.get("latest_quote_display_only")),
        "allowed_for_display": status in {"ready", "stale"},
        "blocking_reasons": sorted(set(blocking_reasons)),
    }
    allowed = _allowed_downstream(payload, status)
    payload.update(
        {
            "allowed_for_feature_store": allowed,
            "allowed_for_training": allowed,
            "allowed_for_prediction": allowed,
            "allowed_for_backtest": allowed,
        }
    )
    validate_no_sample(payload)
    return safe_payload(payload)


class WatermarkStore:
    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir

    @property
    def path(self) -> Path:
        return data_layer_root(self.output_dir) / "watermark.json"

    def load(self) -> dict[str, Any]:
        payload = read_json(self.path, {})
        if isinstance(payload, Mapping) and payload:
            return safe_payload(dict(payload))
        return {
            "schema_version": WATERMARK_SCHEMA_VERSION,
            "status": "blocked",
            "reason": "missing_data_layer_watermark",
            "records": [],
            "records_by_kind": {},
            "blocking_reasons": ["missing_data_layer_watermark"],
            "sample_data_used": False,
            "baseline_used": False,
            "customer_prediction_generated": False,
        }

    def merge_record(
        self,
        *,
        provider_id: str,
        data_kind: str,
        row_count: int,
        fetched_at: str,
        source_published_at: str,
        cache_status: str = "remote",
        stale_status: str = "fresh",
        content_hash: str = "",
        latest_quote_display_only: bool = False,
    ) -> dict[str, Any]:
        return self.merge_records(
            [
                {
                    "provider_id": provider_id,
                    "data_kind": data_kind,
                    "row_count": row_count,
                    "fetched_at": fetched_at,
                    "source_published_at": source_published_at,
                    "cache_status": cache_status,
                    "stale_status": stale_status,
                    "content_hash": content_hash,
                    "latest_quote_display_only": latest_quote_display_only,
                }
            ]
        )

    def merge_records(self, records: list[Mapping[str, Any]]) -> dict[str, Any]:
        normalized = [_normalize_record(record) for record in records]
        records_by_kind = {str(record["data_kind"]): record for record in normalized}
        blocking: list[str] = []
        for record in normalized:
            blocking.extend(str(reason) for reason in record.get("blocking_reasons", []) if str(reason))
        ready_count = sum(1 for record in normalized if record.get("status") == "ready")
        if not normalized:
            status = "blocked"
            blocking.append("missing_data_layer_watermark")
        elif blocking and ready_count:
            status = "degraded"
        elif blocking:
            status = "blocked"
        else:
            status = "ready"
        cache_values = sorted({str(record.get("cache_status") or "") for record in normalized if record.get("cache_status")})
        stale_values = sorted({str(record.get("stale_status") or "") for record in normalized if record.get("stale_status")})
        latest_source = max([str(record.get("source_published_at") or "") for record in normalized] or [""])
        latest_fetch = max([str(record.get("fetched_at") or "") for record in normalized] or [""])
        daily = records_by_kind.get("daily_bar", {})
        payload = {
            "schema_version": WATERMARK_SCHEMA_VERSION,
            "status": status,
            "created_at": utc_now(),
            "records": normalized,
            "records_by_kind": records_by_kind,
            "provider_coverage": normalized,
            "latest_daily": latest_source,
            "source_published_at": latest_source,
            "fetched_at": latest_fetch,
            "cache_status": cache_values[0] if len(cache_values) == 1 else "mixed",
            "stale_status": stale_values[0] if len(stale_values) == 1 else "mixed",
            "sample_data_used": False,
            "baseline_used": False,
            "fake_data_used": False,
            "demo_data_used": False,
            "allowed_for_display": bool(daily.get("allowed_for_display")),
            "allowed_for_feature_store": bool(daily.get("allowed_for_feature_store")),
            "allowed_for_training": bool(daily.get("allowed_for_training")),
            "allowed_for_prediction": bool(daily.get("allowed_for_prediction")),
            "allowed_for_backtest": bool(daily.get("allowed_for_backtest")),
            "customer_prediction_generated": False,
            "blocking_reasons": sorted(set(blocking)),
        }
        validate_no_sample(payload)
        safe = safe_payload(payload)
        atomic_write_json(self.path, safe)
        return safe
