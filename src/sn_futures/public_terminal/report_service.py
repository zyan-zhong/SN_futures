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

    market_ready = bool(daily.get("allowed_for_display") and int(daily.get("row_count") or 0) > 0)
    event_ready = eligible_event_count > 0
    status = "ready" if market_ready else "blocked"

    return _safe(
        {
            "report": {
                "status": status,
                "reason": "" if market_ready else "missing_daily_bars",
                "provider_status": watermark.get("status") or "blocked",
                "market_data_coverage": "ready" if market_ready else "empty",
                "event_coverage": "ready" if event_ready else "empty",
                "event_count": event_count,
                "timed_event_count": eligible_event_count,
                "event_summary": event_summary,
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
