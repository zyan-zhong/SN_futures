from __future__ import annotations

from typing import Any, Mapping


def audit_latency(
    *,
    data_reality: Mapping[str, Any],
    scheduler_state: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    scheduler_state = scheduler_state or {}
    quote_age = data_reality.get("quote_data_age_seconds")
    fetch_age = data_reality.get("fetch_age_seconds")
    warnings: list[str] = []
    if isinstance(quote_age, (int, float)) and quote_age > 1800:
        warnings.append("quote_age_gt_30m")
    if isinstance(fetch_age, (int, float)) and fetch_age > 900:
        warnings.append("fetch_age_gt_15m")
    return {
        "ok": not warnings,
        "status": "passed" if not warnings else "warning",
        "severity": "normal" if not warnings else "yellow",
        "summary": "延迟审计正常" if not warnings else "行情或抓取延迟偏高",
        "warnings": warnings,
        "quote_fetch_latency_ms": scheduler_state.get("quote_fetch_latency_ms"),
        "news_fetch_latency_ms": scheduler_state.get("news_fetch_latency_ms"),
        "feature_build_latency_ms": scheduler_state.get("feature_build_latency_ms"),
        "prediction_latency_ms": scheduler_state.get("prediction_latency_ms"),
        "chart_render_latency_ms": scheduler_state.get("chart_render_latency_ms"),
        "total_refresh_latency_ms": scheduler_state.get("total_refresh_latency_ms"),
        "quote_data_age_seconds": quote_age,
        "fetch_age_seconds": fetch_age,
        "last_market_refresh": scheduler_state.get("last_market_refresh"),
        "last_prediction_refresh": scheduler_state.get("last_prediction_refresh"),
    }
