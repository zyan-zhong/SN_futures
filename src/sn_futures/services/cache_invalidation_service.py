from __future__ import annotations

from datetime import datetime
from typing import Any

from ..api.json_utils import sanitize_for_json
from .api_response_cache import clear_api_response_cache
from .data_watermark_service import update_data_watermark


TERMINAL_CACHE_PREFIXES = (
    "terminal:summary",
    "terminal:snapshot-lite",
    "terminal:snapshot",
    "terminal:data-status",
    "terminal:price-history",
    "terminal:market-analysis",
    "terminal:charts",
    "terminal:reports",
    "terminal:feature",
    "terminal:artifacts",
    "terminal:model-health",
)


def invalidate_terminal_caches(reason: str = "manual") -> dict[str, Any]:
    for prefix in TERMINAL_CACHE_PREFIXES:
        clear_api_response_cache(prefix)
    return sanitize_for_json(
        {
            "status": "success",
            "invalidated_prefixes": list(TERMINAL_CACHE_PREFIXES),
            "reason": str(reason or "manual"),
            "invalidated_at": datetime.now().isoformat(timespec="seconds"),
        }
    )


def invalidate_after_task(kind: str, reason: str | None = None) -> dict[str, Any]:
    task_kind = str(kind or "")
    cache_result = invalidate_terminal_caches(reason=reason or task_kind)
    watermark = update_data_watermark(task_kind, source="task_queue")
    watermark["last_invalidation_reason"] = task_kind
    try:
        from .data_watermark_service import _write_watermark  # type: ignore

        _write_watermark(watermark)
    except Exception:
        pass
    return sanitize_for_json(
        {
            "status": "success",
            "task_kind": task_kind,
            "cache": cache_result,
            "watermark": watermark,
        }
    )
