from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from .stores import atomic_write_json, content_hash, data_layer_root, read_json, safe_part, safe_payload, utc_now, validate_no_sample


EVENT_STORE_SCHEMA_VERSION = "data-layer-event-store-v1"


class EventStore:
    def __init__(self, output_dir: Path | None = None) -> None:
        self.output_dir = output_dir

    @property
    def root(self) -> Path:
        return data_layer_root(self.output_dir) / "events"

    def path_for(self, data_kind: str) -> Path:
        return self.root / f"{safe_part(data_kind, 'event')}.json"

    def persist_event(
        self,
        *,
        provider_id: str,
        data_kind: str,
        event: Mapping[str, Any],
        fetched_at: str = "",
    ) -> dict[str, Any]:
        fetched = str(fetched_at or utc_now())
        source_published_at = str(event.get("source_published_at") or event.get("published_at") or "")
        payload_event = {
            **dict(event),
            "provider_id": str(provider_id or "unknown_provider"),
            "data_kind": str(data_kind or "event"),
            "fetched_at": fetched,
            "source_published_at": source_published_at,
            "event_id": content_hash({"provider_id": provider_id, "data_kind": data_kind, "event": dict(event)}),
            "used_in_model": bool(source_published_at),
            "allowed_for_event_factor": bool(source_published_at),
        }
        if not source_published_at:
            payload_event["used_in_model"] = False
            payload_event["allowed_for_event_factor"] = False
            payload_event["rejection_reason"] = "missing_source_published_at"
        validate_no_sample(payload_event)
        existing = self.load_events(data_kind)
        rows = [*existing, safe_payload(payload_event)]
        published_count = sum(1 for row in rows if str(row.get("source_published_at") or "").strip())
        coverage = round(published_count / len(rows), 4) if rows else 0.0
        manifest = {
            "schema_version": EVENT_STORE_SCHEMA_VERSION,
            "provider_id": str(provider_id or "unknown_provider"),
            "data_kind": str(data_kind or "event"),
            "row_count": len(rows),
            "fetched_at": fetched,
            "source_published_at": source_published_at,
            "source_published_at_coverage": coverage,
            "content_hash": content_hash(rows),
            "sample_data_used": False,
            "baseline_used": False,
            "fake_data_used": False,
            "demo_data_used": False,
            "allowed_for_display": bool(rows),
            "allowed_for_feature_store": False,
            "allowed_for_training": False,
            "allowed_for_prediction": False,
            "allowed_for_backtest": False,
            "blocking_reasons": [] if source_published_at else ["missing_source_published_at"],
        }
        store_payload = {
            "schema_version": EVENT_STORE_SCHEMA_VERSION,
            "data_kind": str(data_kind or "event"),
            "events": rows,
            "manifest": safe_payload(manifest),
        }
        atomic_write_json(self.path_for(data_kind), store_payload)
        return {"event": safe_payload(payload_event), "manifest": safe_payload(manifest)}

    def load_events(self, data_kind: str | None = None) -> list[dict[str, Any]]:
        paths = [self.path_for(data_kind)] if data_kind else list(self.root.glob("*.json"))
        rows: list[dict[str, Any]] = []
        for path in paths:
            payload = read_json(path, {})
            if isinstance(payload, Mapping) and isinstance(payload.get("events"), list):
                rows.extend(dict(row) for row in payload["events"] if isinstance(row, Mapping))
        return safe_payload(rows)
