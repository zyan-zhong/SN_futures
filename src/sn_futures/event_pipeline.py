from __future__ import annotations

from pathlib import Path
from typing import Any

from .event_features import build_event_evidence, sync_event_store_from_news
from .event_store import load_events, load_provider_status, resolve_event_url


def get_event_evidence(
    horizon: str = "tomorrow",
    output_dir: Path | None = None,
    prediction_time: str | None = None,
) -> dict[str, Any]:
    return build_event_evidence(horizon=horizon, output_dir=output_dir, prediction_time=prediction_time)


def get_recent_events(limit: int = 50, category: str = "", min_impact_score: float = 0.0, output_dir: Path | None = None) -> dict[str, Any]:
    sync_event_store_from_news(output_dir)
    rows = load_events(limit=limit, category=category, min_impact_score=min_impact_score)
    return {
        "items": rows,
        "count": len(rows),
        "provider_status": load_provider_status(),
    }


def get_event_provider_status(output_dir: Path | None = None) -> dict[str, Any]:
    sync_event_store_from_news(output_dir)
    rows = load_provider_status()
    return {"items": rows, "count": len(rows)}


def get_event_audit(
    horizon: str = "tomorrow",
    output_dir: Path | None = None,
    prediction_time: str | None = None,
) -> dict[str, Any]:
    payload = get_event_evidence(horizon=horizon, output_dir=output_dir, prediction_time=prediction_time)
    ok = payload.get("used_in_model_event_count", 0) > 0 or payload.get("recognized_event_count", 0) == 0
    reason = ""
    if payload.get("recognized_event_count", 0) > 0 and payload.get("used_in_model_event_count", 0) == 0:
        reason = "recognized_but_not_used"
    return {
        "ok": ok,
        "status": "pass" if ok else "warning",
        "reason": reason,
        **payload,
    }


def open_event_url(event_id: str) -> dict[str, Any]:
    return resolve_event_url(event_id)
