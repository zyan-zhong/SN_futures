from __future__ import annotations

from dataclasses import dataclass
from typing import Any


EVENT_RECORD_SCHEMA_VERSION = "event-record-v1"
EVENT_RECORD_FIELDS: tuple[str, ...] = (
    "event_id",
    "title",
    "summary",
    "url_sanitized",
    "source",
    "provider",
    "region",
    "category",
    "language",
    "source_published_at",
    "fetched_at",
    "available_at",
    "event_time_confidence",
    "relevance_score",
    "source_reliability_score",
    "used_in_model",
    "rejection_reason",
    "content_hash",
)
EVENT_RECORD_REGIONS = ("China", "global")
EVENT_RECORD_CATEGORIES = ("supply", "demand", "inventory", "macro", "exchange", "policy", "geopolitics", "irrelevant")


HORIZON_EVENT_WINDOWS: dict[str, tuple[tuple[str, float], ...]] = {
    "next_5m": (("15m", 0.25), ("30m", 0.5), ("1h", 1.0), ("4h", 4.0)),
    "next_15m": (("1h", 1.0), ("4h", 4.0), ("1d", 24.0)),
    "next_30m": (("4h", 4.0), ("1d", 24.0), ("3d", 72.0)),
    "next_hour": (("4h", 4.0), ("1d", 24.0), ("3d", 72.0), ("7d", 168.0)),
    "tomorrow": (("1d", 24.0), ("3d", 72.0), ("7d", 168.0)),
    "one_to_two_weeks": (("7d", 168.0), ("14d", 336.0), ("30d", 720.0)),
    "one_to_three_months": (("30d", 720.0), ("60d", 1440.0), ("90d", 2160.0)),
}

SOURCE_TIER_BY_PROVIDER: dict[str, str] = {
    "shfe_public": "tier1",
    "shfe_notice": "tier1",
    "shfe_warehouse_receipt": "tier1",
    "shfe_inventory": "tier1",
    "customs_public": "tier1",
    "stats_public": "tier1",
    "miit_policy": "tier1",
    "ndrc_policy": "tier1",
    "mofcom_policy": "tier1",
    "gov_policy": "tier1",
    "public_policy": "tier1",
    "akshare_shmet": "tier2",
    "akshare_cls": "tier2",
    "akshare_news": "tier2",
    "china_nonferrous": "tier2",
    "cnmn_public": "tier2",
    "smm_public": "tier2",
    "mysteel_public": "tier2",
    "futures_daily": "tier2",
    "eastmoney_futures": "tier2",
    "sina_futures": "tier2",
    "newsapi": "tier3",
    "alpha_vantage_news": "tier3",
    "alphavantage_news_fallback": "tier3",
    "eastmoney_quote": "tier3",
    "sina_finance": "tier3",
    "cache": "tier3",
}

SOURCE_TIER_WEIGHT: dict[str, float] = {"tier1": 1.0, "tier2": 0.78, "tier3": 0.55}

EVENT_FEATURE_NAMES: tuple[str, ...] = (
    "event_count",
    "high_impact_event_count",
    "bullish_event_score",
    "bearish_event_score",
    "volatility_event_score",
    "policy_event_count",
    "exchange_notice_flag",
    "supply_disruption_score",
    "demand_positive_score",
    "inventory_event_score",
    "warehouse_receipt_event_score",
    "macro_policy_score",
    "option_iv_event_score",
    "news_sentiment",
    "event_shock_score",
    "authoritative_event_count",
)


@dataclass(frozen=True)
class EventUsageDecision:
    used: bool
    rejected_reason: str


def window_hours_for_horizon(horizon: str) -> tuple[tuple[str, float], ...]:
    return HORIZON_EVENT_WINDOWS.get(horizon, HORIZON_EVENT_WINDOWS["tomorrow"])


def max_window_hours(horizon: str) -> float:
    return max(hours for _, hours in window_hours_for_horizon(horizon))


def source_tier(provider: str, source: str = "") -> str:
    key = str(provider or source or "cache").lower().strip()
    for known, tier in SOURCE_TIER_BY_PROVIDER.items():
        if known in key:
            return tier
    source_text = str(source or "")
    source_lower = source_text.lower()
    if "上期所" in source_text or "上海期货交易所" in source_text or "shfe" in source_lower:
        return "tier1"
    if any(name in source_lower for name in ("smm", "mysteel", "shmet", "期货日报", "有色", "金属网", "eastmoney", "sina")):
        return "tier2"
    return "tier3"


def source_tier_weight(tier: str) -> float:
    return SOURCE_TIER_WEIGHT.get(str(tier), 0.50)


def json_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if isinstance(value, tuple):
        return [str(item) for item in value if str(item).strip()]
    if value is None:
        return []
    return [str(value)] if str(value).strip() else []
