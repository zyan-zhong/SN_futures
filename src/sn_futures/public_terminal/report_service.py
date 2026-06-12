from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..data_layer.watermark import WatermarkStore
from ..utils.secret_sanitizer import sanitize_mapping
from .event_service import build_public_event_center
from .market_service import DOWNSTREAM_FALSE_FLAGS


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def build_public_report(output_dir: Path | None = None) -> dict[str, Any]:
    watermark = WatermarkStore(output_dir=output_dir).load()
    records_by_kind = watermark.get("records_by_kind") if isinstance(watermark.get("records_by_kind"), Mapping) else {}
    daily = records_by_kind.get("daily_bar") if isinstance(records_by_kind.get("daily_bar"), Mapping) else {}
    event_payload = build_public_event_center(output_dir=output_dir)
    event_center = event_payload.get("event_center") if isinstance(event_payload.get("event_center"), Mapping) else {}
    event_summary = event_center.get("summary") if isinstance(event_center.get("summary"), Mapping) else {}
    event_count = int(event_summary.get("total_count") or 0)
    eligible_event_count = int(event_summary.get("eligible_count") or 0)

    daily_rows = int(daily.get("row_count") or 0)
    daily_display_allowed = bool(daily.get("allowed_for_display") and daily_rows > 0)
    daily_stale = daily_display_allowed and str(daily.get("stale_status") or "").lower() == "stale"
    market_ready = daily_display_allowed and not daily_stale
    event_ready = eligible_event_count > 0
    event_section = _safe(
        {
            "status": "ready" if event_count else "blocked",
            "reason": "" if event_count else "missing_events",
            "total_count": event_count,
            "eligible_count": eligible_event_count,
            "rejected_count": int(event_summary.get("rejected_count") or 0),
            "categories": event_summary.get("categories") if isinstance(event_summary.get("categories"), Mapping) else {},
            "regions": event_summary.get("regions") if isinstance(event_summary.get("regions"), Mapping) else {},
            "languages": event_summary.get("languages") if isinstance(event_summary.get("languages"), Mapping) else {},
            "latest_source_published_at": str(event_summary.get("latest_source_published_at") or ""),
            "latest_fetched_at": str(event_summary.get("latest_fetched_at") or ""),
            "investment_advice": False,
            "used_for_customer_prediction": False,
        }
    )
    status = "ready" if market_ready else ("stale" if daily_stale else "blocked")
    reason = "" if market_ready else ("stale_daily_bars" if daily_stale else "missing_daily_bars")
    market_data_coverage = "ready" if market_ready else ("stale" if daily_stale else "empty")

    return _safe(
        {
            "report": {
                "status": status,
                "reason": reason,
                "provider_status": watermark.get("status") or "blocked",
                "market_data_coverage": market_data_coverage,
                "event_coverage": "ready" if event_ready else "empty",
                "event_count": event_count,
                "timed_event_count": eligible_event_count,
                "event_summary": event_summary,
                "event_section": event_section,
                "data_watermark": watermark,
                "research_only": True,
                "investment_advice": False,
                "export_allowed": False,
                "sample_data_used": False,
                "baseline_used": False,
                "customer_prediction_generated": False,
            },
            **DOWNSTREAM_FALSE_FLAGS,
        }
    )
