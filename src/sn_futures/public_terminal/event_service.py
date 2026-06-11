from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..data_layer.event_store import EventStore
from ..data_layer.stores import content_hash
from ..utils.secret_sanitizer import sanitize_mapping
from .market_service import DOWNSTREAM_FALSE_FLAGS


RELEVANCE_THRESHOLD = 0.35

HIGH_SIGNAL_TERMS = {
    "shfe",
    "lme",
    "sn",
    "tin",
    "沪锡",
    "锡",
    "上海期货",
    "上期所",
}

CONTEXT_TERMS = {
    "warehouse",
    "warrant",
    "warrants",
    "inventory",
    "solder",
    "smelter",
    "indonesia",
    "export",
    "quota",
    "policy",
    "futures",
    "exchange",
    "supply",
    "chain",
    "库存",
    "仓单",
    "冶炼",
    "焊料",
    "印尼",
    "出口",
    "政策",
    "交易所",
    "产业链",
}

UNRELATED_TERMS = {
    "coffee",
    "entertainment",
    "football",
    "movie",
    "harvest",
}

PUBLIC_EVENT_CATEGORIES = {
    "china_policy",
    "global_policy",
    "china_news",
    "global_news",
    "exchange_notice",
    "supply_chain_event",
}


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _text(row: Mapping[str, Any]) -> str:
    return " ".join(str(row.get(key) or "") for key in ("title", "summary", "category", "provider_id", "data_kind"))


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _contains_term(text: str, tokens: set[str], term: str) -> bool:
    lower_term = term.lower()
    if re.fullmatch(r"[a-z0-9]+", lower_term):
        return lower_term in tokens
    return lower_term in text.lower()


def _infer_region(row: Mapping[str, Any], text: str) -> str:
    region = str(row.get("region") or "").strip()
    if region:
        return region
    provider = str(row.get("provider_id") or "").lower()
    language = str(row.get("language") or "").lower()
    if provider in {"shfe_public", "public_policy_rss"} or language == "zh" or re.search(r"[\u4e00-\u9fff]", text):
        return "CN"
    return "global"


def _infer_language(row: Mapping[str, Any], text: str) -> str:
    language = str(row.get("language") or "").strip()
    if language:
        return language
    return "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en"


def _infer_category(row: Mapping[str, Any], region: str) -> str:
    existing = str(row.get("category") or "").strip().lower()
    if existing in PUBLIC_EVENT_CATEGORIES:
        return existing
    provider = str(row.get("provider_id") or "").strip().lower()
    data_kind = str(row.get("data_kind") or "").strip().lower()
    if provider == "shfe_public" or data_kind == "exchange_public":
        return "exchange_notice"
    if data_kind == "policy_event" or provider == "public_policy_rss":
        return "china_policy" if region.upper() == "CN" else "global_policy"
    if "supply" in existing or "chain" in existing:
        return "supply_chain_event"
    if data_kind == "news_event":
        return "china_news" if region.upper() == "CN" else "global_news"
    return "global_news"


def _relevance_score(row: Mapping[str, Any]) -> float:
    text = _text(row)
    tokens = _tokens(text)
    high_hits = sum(1 for term in HIGH_SIGNAL_TERMS if _contains_term(text, tokens, term))
    context_hits = sum(1 for term in CONTEXT_TERMS if _contains_term(text, tokens, term))
    unrelated_hits = sum(1 for term in UNRELATED_TERMS if _contains_term(text, tokens, term))
    provider = str(row.get("provider_id") or "").lower()
    category = str(row.get("category") or "").lower()

    score = high_hits * 0.28 + context_hits * 0.08
    if provider == "shfe_public":
        score += 0.1
    if category in {"china_policy", "global_policy", "exchange_notice", "supply_chain_event"}:
        score += 0.05
    if high_hits == 0:
        score = min(score, 0.28)
    if unrelated_hits and high_hits == 0:
        score = min(score, 0.08)
    return round(min(score, 0.98), 2)


def _event_sort_key(event: Mapping[str, Any]) -> tuple[str, str, str]:
    return (
        str(event.get("source_published_at") or ""),
        str(event.get("fetched_at") or ""),
        str(event.get("event_id") or ""),
    )


def _normalize_event(row: Mapping[str, Any]) -> dict[str, Any]:
    text = _text(row)
    region = _infer_region(row, text)
    language = _infer_language(row, text)
    category = _infer_category(row, region)
    enriched = {**dict(row), "category": category, "region": region, "language": language}
    score = _relevance_score(enriched)
    relevant = score >= RELEVANCE_THRESHOLD
    source_published_at = str(row.get("source_published_at") or row.get("published_at") or "").strip()
    fetched_at = str(row.get("fetched_at") or "").strip()
    blocking_reasons: list[str] = []
    if not source_published_at:
        blocking_reasons.append("missing_source_published_at")
    if not relevant:
        blocking_reasons.append("unrelated_to_shfe_sn")
    eligible = bool(source_published_at and relevant)
    event_id = str(row.get("event_id") or content_hash({"event": dict(row)}))

    return _safe(
        {
            "event_id": event_id,
            "title": str(row.get("title") or "Untitled event"),
            "summary": str(row.get("summary") or row.get("title") or ""),
            "url": str(row.get("url") or ""),
            "source_name": str(row.get("source_name") or row.get("provider_id") or "unknown_source"),
            "provider_id": str(row.get("provider_id") or "unknown_provider"),
            "data_kind": str(row.get("data_kind") or "event"),
            "source_published_at": source_published_at,
            "fetched_at": fetched_at,
            "category": category,
            "region": region,
            "language": language,
            "relevance_score": score,
            "relevance_to_shfe_sn": relevant,
            "used_in_model": eligible,
            "eligible_for_event_factor": eligible,
            "allowed_for_event_factor": eligible,
            "blocking_reasons": blocking_reasons,
            "sample_data_used": False,
            "baseline_used": False,
            "fake_data_used": False,
            "demo_data_used": False,
        }
    )


def _counts(events: list[Mapping[str, Any]], field: str) -> dict[str, int]:
    values = [str(event.get(field) or "unknown") for event in events]
    return dict(Counter(values))


def _summary(events: list[Mapping[str, Any]]) -> dict[str, Any]:
    eligible_count = sum(1 for event in events if bool(event.get("eligible_for_event_factor")))
    rejected_count = len(events) - eligible_count
    published = [str(event.get("source_published_at") or "") for event in events if str(event.get("source_published_at") or "")]
    fetched = [str(event.get("fetched_at") or "") for event in events if str(event.get("fetched_at") or "")]
    return _safe(
        {
            "total_count": len(events),
            "eligible_count": eligible_count,
            "rejected_count": rejected_count,
            "categories": _counts(events, "category"),
            "regions": _counts(events, "region"),
            "languages": _counts(events, "language"),
            "latest_source_published_at": max(published) if published else "",
            "latest_fetched_at": max(fetched) if fetched else "",
        }
    )


def build_public_event_center(output_dir: Path | None = None) -> dict[str, Any]:
    rows = EventStore(output_dir=output_dir).load_events()
    events = [_normalize_event(row) for row in rows if isinstance(row, Mapping)]
    events = sorted(events, key=_event_sort_key, reverse=True)
    summary = _summary(events)
    status = "ready" if events else "blocked"
    reason = "" if events else "missing_events"

    return _safe(
        {
            "event_center": {
                "status": status,
                "reason": reason,
                "events": events,
                "summary": summary,
                "categories": summary["categories"],
                "regions": summary["regions"],
                "languages": summary["languages"],
                "sample_data_used": False,
                "baseline_used": False,
                "customer_prediction_generated": False,
            },
            **DOWNSTREAM_FALSE_FLAGS,
        }
    )
