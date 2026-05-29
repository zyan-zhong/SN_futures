"""News and policy impact analysis for SHFE tin (SN).

The analyzer is deliberately transparent.  It only uses articles already
fetched into the local snapshot, attaches source/time/relevance metadata, and
returns zero contribution when sources fail or no tin-relevant article exists.
"""

from __future__ import annotations

import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from .config import ProjectPaths
from .news_store import load_recent_articles


TIN_TERMS = {
    "tin", "lme tin", "shfe tin", "sn futures", "solder", "tin ore", "tin concentrate",
    "锡", "沪锡", "伦锡", "锡矿", "锡锭", "焊锡", "锡精矿", "缅甸锡", "印尼锡",
}
SUPPLY_TERMS = {
    "myanmar", "indonesia", "mine", "ore", "concentrate", "export ban", "shipment",
    "smelter", "maintenance", "strike", "supply", "warehouse", "inventory", "warrant",
    "缅甸", "印尼", "矿山", "锡矿", "出口限制", "出口禁令", "停产", "检修", "罢工",
    "供应", "库存", "仓单", "保税区",
}
DEMAND_TERMS = {
    "semiconductor", "chip", "solder", "photovoltaic", "solar", "electronics", "demand",
    "半导体", "芯片", "焊锡", "光伏", "电子", "消费电子", "需求", "新能源",
}
MACRO_TERMS = {
    "fed", "federal reserve", "dollar", "usd", "yield", "rate cut", "rate hike",
    "inflation", "tariff", "pmi", "美元", "美联储", "利率", "降息", "加息", "汇率",
    "通胀", "关税", "央行", "政策",
}
POSITIVE_TERMS = {
    "shortage", "tight", "disruption", "cut", "ban", "halt", "strike", "lower inventory",
    "stimulus", "support", "surge demand", "short supply",
    "短缺", "偏紧", "扰动", "停产", "禁令", "罢工", "库存下降", "去库", "刺激",
    "支持", "需求增长", "供应收缩", "检修",
}
NEGATIVE_TERMS = {
    "surplus", "weak demand", "slowdown", "higher inventory", "recession", "oversupply",
    "restart", "resume", "hawkish", "rate hike", "strong dollar",
    "过剩", "需求疲弱", "放缓", "库存增加", "累库", "衰退", "供应恢复", "复产",
    "鹰派", "加息", "美元走强",
}

SOURCE_TRUST = {
    "newsapi": 0.80,
    "alpha_vantage_news": 0.70,
    "alphavantage_news_fallback": 0.68,
    "shfe_public": 0.88,
    "public_policy": 0.72,
    "akshare_shmet": 0.78,
    "akshare_cls": 0.70,
    "cache": 0.50,
}


@dataclass
class NewsPolicyItem:
    event_id: str
    title: str
    source: str
    published_at: str
    url: str
    event_type: str
    sentiment: float
    impact_level: str
    relevance_score: float
    event_decay_weight: float
    source_trust: float
    confidence_weight: float
    direction_contribution: str
    enters_model: bool
    evidence: str


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        x = float(value)
    except Exception:
        return default
    return x if math.isfinite(x) else default


def _contains_any(text: str, terms: Iterable[str]) -> bool:
    lower = text.lower()
    for term in terms:
        needle = term.lower().strip()
        if not needle:
            continue
        # English terms such as "tin" must be matched as whole words.
        # Otherwise words like "investing" or "position" pollute the tin
        # news factor and make unrelated ETF headlines look relevant.
        if needle.isascii() and any(ch.isalpha() for ch in needle):
            pattern = r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])"
            if re.search(pattern, lower):
                return True
            continue
        if needle in lower:
            return True
    return False


def _article_text(article: Mapping[str, Any]) -> str:
    return " ".join(
        str(article.get(key, "") or "")
        for key in ("title", "description", "summary", "content")
    )


def _source_name(article: Mapping[str, Any]) -> str:
    src = article.get("source")
    if isinstance(src, Mapping):
        return str(src.get("name") or src.get("id") or "unknown")
    return str(src or article.get("provider") or "unknown")


def _source_key(article: Mapping[str, Any]) -> str:
    provider = str(article.get("provider") or article.get("source_name") or "").lower()
    if "alpha" in provider:
        return "alpha_vantage_news"
    if "shfe" in provider or "上期所" in provider:
        return "shfe_public"
    if "shmet" in provider:
        return "akshare_shmet"
    if "cls" in provider:
        return "akshare_cls"
    if "policy" in provider:
        return "public_policy"
    if "newsapi" in provider or article.get("source"):
        return "newsapi"
    return provider or "cache"


def _published_at(article: Mapping[str, Any]) -> str:
    for key in ("publishedAt", "time_published", "published_at", "datetime", "date"):
        value = article.get(key)
        if value:
            text = str(value)
            if len(text) == 8 and text.isdigit():
                return f"{text[:4]}-{text[4:6]}-{text[6:8]}T00:00:00"
            if len(text) >= 13 and text[:8].isdigit():
                return f"{text[:4]}-{text[4:6]}-{text[6:8]}T{text[9:11]}:{text[11:13]}:00"
            return text
    return ""


def _relevance(text: str) -> float:
    lower = text.lower()
    score = 0.0
    if _contains_any(lower, TIN_TERMS):
        score += 0.55
    if _contains_any(lower, SUPPLY_TERMS):
        score += 0.22
    if _contains_any(lower, DEMAND_TERMS):
        score += 0.15
    if _contains_any(lower, MACRO_TERMS):
        score += 0.08
    return min(score, 1.0)


def _event_type(text: str) -> str:
    if _contains_any(text, {"缅甸", "印尼", "myanmar", "indonesia", "锡矿", "mine", "ore", "export ban", "出口"}):
        return "矿端/海外供应"
    if _contains_any(text, {"库存", "仓单", "warehouse", "inventory", "warrant"}):
        return "库存仓单"
    if _contains_any(text, {"冶炼", "smelter", "检修", "maintenance"}):
        return "冶炼检修"
    if _contains_any(text, DEMAND_TERMS):
        return "下游需求"
    if _contains_any(text, MACRO_TERMS):
        return "宏观政策"
    return "一般相关新闻"


def _sentiment(text: str, event_type: str) -> float:
    positive = sum(1 for t in POSITIVE_TERMS if t.lower() in text.lower())
    negative = sum(1 for t in NEGATIVE_TERMS if t.lower() in text.lower())
    raw = positive - negative
    if raw == 0:
        # Supply-side disruptions are usually price supportive for tin, while
        # demand weakness is negative.  Keep this small unless explicit words
        # are present.
        if event_type in {"矿端/海外供应", "冶炼检修"} and _contains_any(text, {"停产", "罢工", "export ban", "disruption", "maintenance"}):
            raw = 1
        elif event_type == "下游需求" and _contains_any(text, {"weak", "疲弱", "放缓"}):
            raw = -1
    return max(-1.0, min(1.0, raw / 3.0))


def _impact_level(text: str, relevance: float) -> str:
    if relevance >= 0.75 and _contains_any(text, {"禁令", "停产", "罢工", "export ban", "halt", "strike", "美联储", "fed"}):
        return "重大"
    if relevance >= 0.55:
        return "一般"
    return "轻微"


def _decay_weight(published_at: str, now: Optional[datetime] = None) -> float:
    if not published_at:
        return 0.35
    now = now or datetime.now()
    text = published_at.replace("Z", "+00:00")
    try:
        ts = datetime.fromisoformat(text)
        if ts.tzinfo is not None:
            ts = ts.astimezone().replace(tzinfo=None)
    except Exception:
        return 0.45
    age_hours = max(0.0, (now - ts).total_seconds() / 3600.0)
    return max(0.10, min(1.0, math.exp(-age_hours / 36.0)))


def _direction_label(sentiment: float) -> str:
    if sentiment > 0.12:
        return "偏多"
    if sentiment < -0.12:
        return "偏空"
    return "中性"


def _source_status(snapshot: Mapping[str, Any]) -> Dict[str, Any]:
    rows = snapshot.get("source_status", [])
    status: Dict[str, Any] = {}
    if isinstance(rows, list):
        for row in rows:
            if not isinstance(row, Mapping):
                continue
            name = str(row.get("name") or row.get("source") or "unknown")
            status[name] = {
                "ok": bool(row.get("ok", row.get("success", False))),
                "from_cache": bool(row.get("from_cache", False)),
                "limited": bool(row.get("limited", False)),
                "message": str(row.get("message") or row.get("error") or ""),
                "updated_at": str(row.get("updated_at") or row.get("ts") or ""),
            }
    return status


def _analyze_articles(articles: Iterable[Mapping[str, Any]]) -> List[NewsPolicyItem]:
    items: List[NewsPolicyItem] = []
    now = datetime.now()
    for article in articles:
        if not isinstance(article, Mapping):
            continue
        text = _article_text(article)
        relevance = _relevance(text)
        if relevance < 0.25:
            continue
        event_type = _event_type(text)
        sentiment = _sentiment(text, event_type)
        published_at = _published_at(article)
        decay = _decay_weight(published_at, now=now)
        source_key = _source_key(article)
        trust = SOURCE_TRUST.get(source_key, 0.55)
        impact = _impact_level(text, relevance)
        impact_multiplier = {"重大": 1.0, "一般": 0.62, "轻微": 0.32}.get(impact, 0.32)
        confidence_weight = relevance * decay * trust * impact_multiplier
        enters_model = confidence_weight >= 0.08 and abs(sentiment) >= 0.05
        title = str(article.get("title") or article.get("summary") or "未命名新闻")
        items.append(
            NewsPolicyItem(
                event_id=str(article.get("event_id") or ""),
                title=title[:160],
                source=_source_name(article),
                published_at=published_at,
                url=str(article.get("url") or ""),
                event_type=event_type,
                sentiment=round(sentiment, 4),
                impact_level=impact,
                relevance_score=round(relevance, 4),
                event_decay_weight=round(decay, 4),
                source_trust=round(trust, 4),
                confidence_weight=round(confidence_weight, 4),
                direction_contribution=_direction_label(sentiment),
                enters_model=enters_model,
                evidence=f"{event_type}，{impact}影响，{_direction_label(sentiment)}",
            )
        )
    items.sort(key=lambda x: (x.enters_model, x.confidence_weight, x.published_at), reverse=True)
    return items[:30]


def analyze_news_policy(output_dir: Path | None = None) -> Dict[str, Any]:
    out = output_dir or ProjectPaths().output_dir
    snapshot_path = out / "sn_live_snapshot.json"
    try:
        import json

        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8")) if snapshot_path.exists() else {}
    except Exception:
        snapshot = {}
    snapshot_articles = snapshot.get("articles", []) if isinstance(snapshot.get("articles"), list) else []
    stored_articles = load_recent_articles(limit=120)
    articles = list(snapshot_articles or [])
    seen = {str(item.get("url") or item.get("title")) for item in articles if isinstance(item, Mapping)}
    for item in stored_articles:
        key = str(item.get("url") or item.get("title"))
        if key and key not in seen:
            articles.append(item)
            seen.add(key)
    status = _source_status(snapshot)
    items = _analyze_articles(articles)
    included = [item for item in items if item.enters_model]
    weight_sum = sum(item.confidence_weight for item in included)
    weighted_sentiment = (
        sum(item.sentiment * item.confidence_weight for item in included) / weight_sum
        if weight_sum > 0
        else 0.0
    )
    confidence_weight = min(1.0, weight_sum)
    failed_sources = [
        name for name, row in status.items()
        if not bool(row.get("ok")) and name in {"newsapi", "alpha_vantage_news", "alphavantage_news_fallback"}
    ]
    failure_reason = ""
    if not included:
        if failed_sources:
            failure_reason = "新闻源失败或限流，新闻因子暂不入模"
        elif articles:
            failure_reason = "抓取到新闻但锡相关性或影响强度不足"
        else:
            failure_reason = "暂无可用新闻缓存"
    direction = _direction_label(weighted_sentiment)
    refresh_at = str(snapshot.get("generated_at") or "")
    next_refresh_at = ""
    try:
        next_refresh_at = (datetime.fromisoformat(refresh_at) + timedelta(minutes=5)).isoformat(timespec="seconds")
    except Exception:
        pass
    event_factors = [
        {
            "event_type": item.event_type,
            "direction": item.direction_contribution,
            "weight": item.confidence_weight,
            "impact_level": item.impact_level,
            "title": item.title,
            "source": item.source,
        }
        for item in included[:8]
    ]
    latest_headlines = [
        {
            "event_id": item.event_id,
            "title": item.title,
            "source": item.source,
            "published_at": item.published_at,
            "event_type": item.event_type,
            "sentiment": item.sentiment,
            "impact_level": item.impact_level,
            "enters_model": item.enters_model,
            "source_url": item.url,
            "url": item.url,
        }
        for item in items[:8]
    ]
    summary = {
        "article_count": len(articles),
        "recognized_count": len(items),
        "included_count": len(included),
        "weighted_sentiment": round(weighted_sentiment, 4),
        "direction_bias": direction,
        "direction_contribution": f"新闻政策因子{direction}，可信权重 {confidence_weight:.2f}",
        "contribution_label": f"新闻政策因子{direction}，可信权重 {confidence_weight:.2f}",
        "confidence_weight": round(confidence_weight, 4),
        "failure_reason": failure_reason,
        "failed_sources": failed_sources,
        "refresh_at": refresh_at,
        "next_refresh_at": next_refresh_at,
        "latest_headlines": latest_headlines,
        "event_factors": event_factors,
        "provider_status": status,
    }
    return {
        "summary": summary,
        "items": [asdict(item) for item in items],
        "source_status": status,
        "provider_status": status,
        "refresh_at": refresh_at,
        "next_refresh_at": next_refresh_at,
        "event_factors": event_factors,
        "direction_contribution": summary["direction_contribution"],
        "confidence_weight": summary["confidence_weight"],
        "disclaimer": "本内容仅为期货投研参考，不构成任何投资建议，期货交易有风险，投资需谨慎。",
    }


def news_policy_direction_score(output_dir: Path | None = None) -> float:
    analysis = analyze_news_policy(output_dir)
    summary = analysis.get("summary", {})
    sentiment = _safe_float(summary.get("weighted_sentiment"), 0.0)
    confidence = _safe_float(summary.get("confidence_weight"), 0.0)
    return max(-1.0, min(1.0, sentiment * (0.35 + confidence)))
