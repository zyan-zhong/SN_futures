from __future__ import annotations

import json
import math
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


STRONG_TIN_KEYWORDS = (
    "LME tin",
    "SHFE tin",
    "Shanghai tin",
    "Shanghai Futures Exchange tin",
    "沪锡",
    "锡期货",
    "上期所锡",
)
PLAIN_TIN_KEYWORDS = ("tin", "锡")
SHFE_LME_KEYWORDS = ("SHFE", "LME", "Shanghai Futures Exchange", "沪锡", "上期所", "伦锡")
SUPPLY_KEYWORDS = (
    "Indonesia",
    "Myanmar",
    "Wa State",
    "Man Maw",
    "mine",
    "mining",
    "smelter",
    "concentrate",
    "export quota",
    "export permit",
    "suspension",
    "缅甸",
    "佤邦",
    "曼相",
    "印尼",
    "冶炼",
    "锡矿",
    "精矿",
    "出口",
    "配额",
    "停产",
    "供应",
)
DEMAND_KEYWORDS = (
    "semiconductor",
    "solder",
    "photovoltaic",
    "solar",
    "electronics",
    "PCB",
    "半导体",
    "焊料",
    "光伏",
    "电子",
)
INVENTORY_KEYWORDS = (
    "inventory",
    "warehouse",
    "warrant",
    "stockpile",
    "stockpiles",
    "库存",
    "仓单",
    "升贴水",
)
MACRO_KEYWORDS = (
    "FOMC",
    "dollar",
    "rate",
    "yield",
    "treasury",
    "Fed",
    "policy",
    "美元",
    "利率",
    "美联储",
    "政策",
)
NEGATIVE_KEYWORDS = (
    "Macworld",
    "PyPI",
    "Python package",
    "software package",
    "iPhone",
    "Apple",
    "Apple review",
    "GitHub",
    "App Store",
    "browser plugin",
    "audio DAC",
    "DAC",
    "sports",
    "entertainment",
    "tin can",
    "canned food",
    "tin foil",
    "home decor",
    "food packaging",
    "packaging",
    "Tinymce",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _events_dir() -> Path:
    path = get_user_output_dir() / "events"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _source_name(source: Any) -> str:
    if isinstance(source, Mapping):
        return str(source.get("name") or "")
    return str(source or "")


def _text(article: Mapping[str, Any]) -> str:
    parts = [
        str(article.get("title") or ""),
        str(article.get("description") or ""),
        str(article.get("summary_zh") or ""),
        str(article.get("content") or ""),
        _source_name(article.get("source")),
    ]
    return " ".join(parts)


def _contains_tin_word(text_lower: str) -> bool:
    return bool(re.search(r"(?<![a-z])tin(?![a-z])", text_lower)) or "锡" in text_lower


def _keyword_hits(text: str, keywords: tuple[str, ...]) -> list[str]:
    lower = text.lower()
    hits: list[str] = []
    for keyword in keywords:
        key_lower = keyword.lower()
        if key_lower == "tin":
            if _contains_tin_word(lower):
                hits.append(keyword)
            continue
        if key_lower in lower:
            hits.append(keyword)
    return hits


def _score_from_hits(hits: list[str], *, divisor: float = 2.0, cap: float = 1.0) -> float:
    if not hits:
        return 0.0
    return min(cap, len(hits) / divisor)


def _round(value: float) -> float:
    if not math.isfinite(value):
        return 0.0
    return round(max(0.0, min(1.0, value)), 4)


def _published_date(event: Mapping[str, Any]) -> str:
    raw = str(event.get("published_at") or event.get("publishedAt") or event.get("time") or "")[:10]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", raw):
        return raw
    return _now()[:10]


def score_news_relevance(article: Mapping[str, Any]) -> dict[str, Any]:
    """Score whether a news item is actually relevant to tin fundamentals."""

    text = _text(article)
    lower = text.lower()
    negative_hits = _keyword_hits(text, NEGATIVE_KEYWORDS)
    strong_tin_hits = _keyword_hits(text, STRONG_TIN_KEYWORDS)
    plain_tin_hits = _keyword_hits(text, PLAIN_TIN_KEYWORDS)
    shfe_lme_hits = _keyword_hits(text, SHFE_LME_KEYWORDS)
    supply_hits = _keyword_hits(text, SUPPLY_KEYWORDS)
    demand_hits = _keyword_hits(text, DEMAND_KEYWORDS)
    inventory_hits = _keyword_hits(text, INVENTORY_KEYWORDS)
    macro_hits = _keyword_hits(text, MACRO_KEYWORDS)

    negative_keyword_penalty = min(0.85, len(negative_hits) * 0.25)
    plain_tin_valid = bool(plain_tin_hits) and negative_keyword_penalty < 0.4
    tin_entity_score = 1.0 if strong_tin_hits else (0.55 if plain_tin_valid else 0.0)
    shfe_lme_score = _score_from_hits(shfe_lme_hits, divisor=2.0, cap=0.9)
    exchange_score = _score_from_hits(shfe_lme_hits + inventory_hits, divisor=3.0, cap=1.0)
    supply_chain_score = _score_from_hits(supply_hits, divisor=2.0, cap=1.0)
    demand_chain_score = _score_from_hits(demand_hits, divisor=2.0, cap=1.0)
    inventory_score = _score_from_hits(inventory_hits, divisor=2.0, cap=1.0)
    macro_score = _score_from_hits(macro_hits, divisor=3.0, cap=0.8)

    chain_score = max(supply_chain_score, demand_chain_score, inventory_score, exchange_score, macro_score)
    raw_score = (
        0.34 * tin_entity_score
        + 0.18 * shfe_lme_score
        + 0.25 * chain_score
        + 0.15 * exchange_score
        + 0.08 * (supply_chain_score + demand_chain_score + inventory_score + macro_score) / 4.0
    )
    if strong_tin_hits and (supply_hits or demand_hits or inventory_hits or shfe_lme_hits):
        raw_score += 0.08
    if plain_tin_hits and any(term in lower for term in ("can", "foil", "package", "packaging")):
        raw_score -= 0.2
    relevance_score = _round(raw_score - negative_keyword_penalty)
    display_relevant = relevance_score >= 0.25

    category = "irrelevant"
    category_scores = {
        "supply": supply_chain_score,
        "inventory": inventory_score,
        "exchange": exchange_score,
        "demand": demand_chain_score,
        "macro": macro_score,
    }
    best_category, best_score = max(category_scores.items(), key=lambda item: item[1])
    if tin_entity_score > 0 and best_score > 0:
        category = best_category
    elif tin_entity_score > 0 and shfe_lme_score > 0:
        category = "exchange"

    keyword_hits = list(
        dict.fromkeys(strong_tin_hits + plain_tin_hits + shfe_lme_hits + supply_hits + demand_hits + inventory_hits + macro_hits)
    )
    used_in_model = (
        relevance_score >= 0.55
        and tin_entity_score > 0
        and category != "irrelevant"
        and negative_keyword_penalty < 0.4
        and bool(keyword_hits)
    )

    exclusion_reason = ""
    if not used_in_model:
        if negative_keyword_penalty >= 0.4:
            exclusion_reason = "命中软件、消费电子、食品罐头或娱乐等负面关键词，排除入模。"
        elif tin_entity_score <= 0:
            exclusion_reason = "未命中沪锡、LME tin、SHFE tin 或有效锡产业实体。"
        elif category == "irrelevant":
            exclusion_reason = "缺少供应、需求、库存、交易所或宏观证据。"
        elif relevance_score < 0.25:
            exclusion_reason = "低于展示相关性门槛。"
        else:
            exclusion_reason = "未达到入模相关性门槛，仅用于人工浏览。"

    return {
        "tin_entity_score": _round(tin_entity_score),
        "shfe_lme_score": _round(shfe_lme_score),
        "exchange_score": _round(exchange_score),
        "supply_chain_score": _round(supply_chain_score),
        "demand_chain_score": _round(demand_chain_score),
        "inventory_score": _round(inventory_score),
        "macro_score": _round(macro_score),
        "negative_keyword_penalty": _round(negative_keyword_penalty),
        "relevance_score": _round(relevance_score),
        "used_in_model": used_in_model,
        "allowed_for_event_factor": used_in_model,
        "display_relevant": display_relevant,
        "category": category,
        "sentiment_score": round(max(-1.0, min(1.0, supply_chain_score + demand_chain_score + inventory_score - negative_keyword_penalty)) / 3.0, 4),
        "impact_score": _round(max(supply_chain_score, demand_chain_score, inventory_score, exchange_score, macro_score)),
        "exclusion_reason": exclusion_reason,
        "summary_zh": (
            "高相关锡产业事件，可进入事件因子。"
            if used_in_model
            else ("低相关或仅供浏览，不进入模型因子。" if display_relevant else "相关性过低，默认不展示、不入模。")
        ),
        "keyword_hits": keyword_hits,
        "negative_keyword_hits": negative_hits,
    }


def apply_news_relevance(events: list[Mapping[str, Any]]) -> dict[str, Any]:
    enhanced: list[dict[str, Any]] = []
    high: list[dict[str, Any]] = []
    low: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    for event in events:
        scored = dict(event)
        scored.update(score_news_relevance(event))
        if scored["used_in_model"]:
            high.append(scored)
        elif scored["display_relevant"]:
            low.append(scored)
        else:
            rejected.append(scored)
        enhanced.append(scored)
    return {
        "events": enhanced,
        "high_relevance_events": high,
        "low_relevance_events": low,
        "rejected_events": rejected,
        "used_in_model_count": len(high),
        "low_relevance_count": len(low),
        "rejected_count": len(rejected),
    }


def _aggregate_event_factor_inputs(events: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[_published_date(event)].append(event)

    inputs: list[dict[str, Any]] = []
    for trade_date in sorted(grouped):
        rows = grouped[trade_date]
        relevance_values = [float(row.get("relevance_score") or 0.0) for row in rows]
        inputs.append(
            {
                "trade_date": trade_date,
                "news_count": len(rows),
                "used_in_model_count": len(rows),
                "supply_shock_score": round(sum(float(row.get("supply_chain_score") or 0.0) for row in rows), 4),
                "demand_shock_score": round(sum(float(row.get("demand_chain_score") or 0.0) for row in rows), 4),
                "inventory_shock_score": round(sum(float(row.get("inventory_score") or 0.0) for row in rows), 4),
                "macro_risk_score": round(sum(float(row.get("macro_score") or 0.0) for row in rows), 4),
                "exchange_event_score": round(sum(float(row.get("exchange_score") or 0.0) for row in rows), 4),
                "event_recency_decay_score": 1.0,
                "max_relevance_score": round(max(relevance_values) if relevance_values else 0.0, 4),
                "avg_relevance_score": round(sum(relevance_values) / len(relevance_values) if relevance_values else 0.0, 4),
            }
        )
    return inputs


def _query_group_performance(events: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for event in events:
        grouped[str(event.get("query_group") or "unknown")].append(event)
    summary: list[dict[str, Any]] = []
    for group in sorted(grouped):
        rows = grouped[group]
        used = [row for row in rows if row.get("used_in_model")]
        relevance = [float(row.get("relevance_score") or 0.0) for row in rows]
        summary.append(
            {
                "query_group": group,
                "returned_count": len(rows),
                "used_in_model_count": len(used),
                "avg_relevance": round(sum(relevance) / len(relevance) if relevance else 0.0, 4),
            }
        )
    return summary


def refresh_news_relevance() -> dict[str, Any]:
    events_dir = _events_dir()
    source_path = events_dir / "news_events.json"
    payload = _read_json(source_path)
    rows = payload.get("events", []) if isinstance(payload, Mapping) and isinstance(payload.get("events"), list) else []
    events = [row for row in rows if isinstance(row, Mapping)]
    result = apply_news_relevance(events)
    inputs = _aggregate_event_factor_inputs(result["high_relevance_events"])
    now = _now()
    no_model_events = result["used_in_model_count"] == 0
    status = {
        "source_name": "news_relevance",
        "enabled": True,
        "configured": True,
        "attempted": True,
        "success": True,
        "row_count": len(events),
        "used_in_model_count": result["used_in_model_count"],
        "message_zh": (
            "本周期无通过相关性门槛的锡产业新闻；系统不会伪造事件因子。"
            if no_model_events
            else "新闻相关性过滤完成；仅高相关新闻进入事件因子。"
        ),
        "last_attempt_time": now,
        "last_success_time": now,
        "next_actions_zh": ["在事件监控页查看入模/未入模标记", "低相关新闻只用于人工浏览"],
    }
    factor_payload = {
        "events": result["high_relevance_events"],
        "inputs": inputs,
        "used_in_model_count": result["used_in_model_count"],
        "message_zh": (
            "本周期无通过相关性门槛的锡产业新闻。"
            if no_model_events
            else "仅 used_in_model=true 的高相关新闻进入事件因子。"
        ),
        "generated_at": now,
    }
    report_payload = {
        "raw_count": len(events),
        "candidate_count": len(events),
        "used_in_model_count": result["used_in_model_count"],
        "low_relevance_count": result["low_relevance_count"],
        "rejected_count": result["rejected_count"],
        "excluded_count": result["low_relevance_count"] + result["rejected_count"],
        "high_relevance_events": result["high_relevance_events"],
        "low_relevance_events": result["low_relevance_events"],
        "rejected_events": result["rejected_events"],
        "query_group_performance": _query_group_performance(result["events"]),
        "message_zh": "新闻相关性报告已生成；未入模新闻不会进入事件因子。",
        "generated_at": now,
    }
    _write_json(events_dir / "news_events_relevance.json", {**result, "generated_at": now, "status": status})
    _write_json(events_dir / "news_events_filtered.json", {"events": result["high_relevance_events"], "generated_at": now, "status": status})
    _write_json(events_dir / "event_factor_inputs.json", factor_payload)
    _write_json(events_dir / "news_relevance_report.json", report_payload)
    _write_json(events_dir / "news_events.json", {"events": result["events"], "generated_at": now, "status": status})
    _write_json(events_dir / "news_relevance_status.json", status)
    return sanitize_for_json(
        {
            "status": "success",
            "message_zh": status["message_zh"],
            "row_count": len(events),
            "used_in_model_count": result["used_in_model_count"],
            "output_files": [
                str(events_dir / "news_events_relevance.json"),
                str(events_dir / "news_events_filtered.json"),
                str(events_dir / "event_factor_inputs.json"),
                str(events_dir / "news_relevance_report.json"),
                str(events_dir / "news_events.json"),
                str(events_dir / "news_relevance_status.json"),
            ],
            "next_actions_zh": status["next_actions_zh"],
        }
    )
