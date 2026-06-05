from __future__ import annotations

import hashlib
import math
import re
from typing import Any, Mapping
from urllib.parse import urlparse

import pandas as pd

from .event_schema import source_tier, source_tier_weight
from .event_url_resolver import resolve_canonical_url


TIN_TERMS = {
    "沪锡", "锡", "SN", "sn", "沪锡主连", "锡期货", "锡期权", "锡锭", "精炼锡", "锡矿", "锡矿砂", "锡精矿",
    "焊锡", "焊料", "马口铁", "半导体", "电子制造", "光伏", "缅甸", "佤邦", "印尼", "伦锡", "上期所锡",
    "LME tin", "SHFE tin", "tin", "solder", "tin ore", "tin concentrate",
}
SUPPLY_TERMS = {
    "供应", "停产", "复产", "检修", "矿山", "锡矿", "缅甸", "佤邦", "印尼", "刚果", "秘鲁", "玻利维亚",
    "出口限制", "出口禁令", "进口", "海关", "冶炼", "开工率", "产量", "短缺", "扰动",
    "supply", "mine", "myanmar", "indonesia", "export ban", "smelter", "maintenance",
}
DEMAND_TERMS = {
    "需求", "半导体", "芯片", "电子", "电子制造", "光伏", "焊锡", "焊料", "新能源", "消费电子",
    "demand", "semiconductor", "chip", "electronics", "photovoltaic", "solar", "solder",
}
INVENTORY_TERMS = {"库存", "仓单", "注册仓单", "注销仓单", "升水", "贴水", "基差", "inventory", "warrant", "warehouse"}
EXCHANGE_TERMS = {"上期所", "SHFE", "公告", "通知", "保证金", "手续费", "涨跌停", "限仓", "交易限额", "交割", "结算"}
MACRO_TERMS = {
    "美元", "汇率", "人民币", "美联储", "加息", "降息", "议息", "利率", "通胀", "CPI", "PPI", "PMI",
    "工业增加值", "社融", "央行", "政策", "关税", "国庆", "春节", "劳动节", "端午", "中秋",
    "fed", "fomc", "dollar", "usd", "rate", "inflation", "holiday",
}
OPTION_TERMS = {"期权", "隐含波动率", "Delta", "iv", "option"}

BULLISH_TERMS = {
    "停产", "罢工", "中断", "禁令", "出口限制", "供应收缩", "供应偏紧", "库存下降", "仓单下降", "注销仓单",
    "升水扩大", "需求改善", "需求回暖", "复苏", "短缺", "进口减少", "美元走弱", "降息",
    "support", "shortage", "disruption",
}
BEARISH_TERMS = {
    "复产", "恢复", "供应增加", "库存增加", "仓单增加", "累库", "贴水扩大", "需求疲弱", "需求下滑",
    "进口增加", "美元走强", "加息", "over supply", "oversupply", "weak demand", "restart", "higher inventory",
}
VOLATILITY_TERMS = {"保证金", "涨跌停", "交易限额", "手续费", "风险", "异动", "监管", "地缘", "不确定", "uncertain", "volatility"}


def _contains_any(text: str, terms: set[str]) -> bool:
    lower = text.lower()
    for term in terms:
        needle = term.lower().strip()
        if not needle:
            continue
        if needle.isascii() and any(ch.isalpha() for ch in needle):
            if re.search(r"(?<![a-z0-9])" + re.escape(needle) + r"(?![a-z0-9])", lower):
                return True
            continue
        if needle in lower:
            return True
    return False


def _count_terms(text: str, terms: set[str]) -> int:
    lower = text.lower()
    return sum(1 for term in terms if term and term.lower() in lower)


def safe_url(url: str) -> str:
    raw = str(url or "").strip()
    parsed = urlparse(raw)
    if parsed.scheme.lower() in {"http", "https"} and parsed.netloc:
        return raw
    return ""


def parse_time(value: Any) -> pd.Timestamp | None:
    if not value:
        return None
    try:
        ts = pd.Timestamp(str(value))
        if ts.tzinfo is None:
            ts = ts.tz_localize("Asia/Hong_Kong")
        else:
            ts = ts.tz_convert("Asia/Hong_Kong")
        return ts
    except Exception:
        return None


def _article_text(article: Mapping[str, Any]) -> str:
    return " ".join(str(article.get(key, "") or "") for key in ("title", "summary", "description", "content", "raw_text"))


def _source(article: Mapping[str, Any]) -> str:
    src = article.get("source")
    if isinstance(src, Mapping):
        return str(src.get("name") or src.get("id") or article.get("provider") or "公开来源")
    return str(src or article.get("provider") or "公开来源")


def _provider(article: Mapping[str, Any]) -> str:
    return str(article.get("provider") or article.get("source_tier") or _source(article) or "cache")


def _published_at(article: Mapping[str, Any]) -> str:
    for key in ("source_published_at", "published_at", "publishedAt", "time_published", "datetime", "date"):
        if article.get(key):
            return str(article.get(key))
    return ""


def _event_time_confidence(source_published_at: str) -> float:
    if not source_published_at:
        return 0.25
    return 1.0 if parse_time(source_published_at) is not None else 0.40


def _region(article: Mapping[str, Any], provider: str, source: str, url: str) -> str:
    explicit = str(article.get("region") or "").strip().lower()
    if explicit in {"china", "中国", "cn"}:
        return "China"
    if explicit in {"global", "international", "world"}:
        return "global"
    text = f"{provider} {source} {url}".lower()
    if any(key in text for key in ("shfe", "miit", "ndrc", "mofcom", ".gov.cn", ".cn/")):
        return "China"
    return "global"


def _language(article: Mapping[str, Any], text: str) -> str:
    explicit = str(article.get("language") or article.get("query_language") or "").strip().lower()
    if explicit in {"zh", "zh-cn", "cn"}:
        return "zh"
    if explicit in {"en", "english"}:
        return "en"
    return "zh" if re.search(r"[\u4e00-\u9fff]", text) else "en"


def _event_type(text: str) -> str:
    if _contains_any(text, EXCHANGE_TERMS):
        if _contains_any(text, {"保证金", "手续费", "涨跌停", "限仓", "交易限额"}):
            return "margin_change"
        return "exchange_notice"
    if _contains_any(text, INVENTORY_TERMS):
        if _contains_any(text, {"仓单", "注册仓单", "注销仓单", "warrant"}):
            return "warehouse_receipt_change"
        return "inventory_change"
    if _contains_any(text, {"缅甸", "佤邦", "印尼", "刚果", "秘鲁", "玻利维亚", "出口限制", "出口禁令", "矿山", "停产", "罢工", "myanmar", "indonesia"}):
        return "supply_disruption"
    if _contains_any(text, {"冶炼", "检修", "开工率", "产量", "smelter", "maintenance"}):
        return "smelter_output_change"
    if _contains_any(text, {"进口", "出口", "海关", "锡矿砂", "锡精矿", "import", "export"}):
        return "import_export"
    if _contains_any(text, DEMAND_TERMS):
        return "downstream_demand"
    if _contains_any(text, MACRO_TERMS):
        return "macro_policy"
    if _contains_any(text, OPTION_TERMS):
        return "option_iv_change"
    return "general_tin_news"


def _category(event_type: str) -> str:
    if event_type in {"exchange_notice", "margin_change", "fee_change", "limit_change"}:
        return "交易所公告"
    if event_type in {"warehouse_receipt_change", "inventory_change"}:
        return "库存仓单"
    if event_type in {"supply_disruption", "smelter_output_change", "import_export"}:
        return "供应端"
    if event_type == "downstream_demand":
        return "需求端"
    if event_type == "macro_policy":
        return "宏观政策"
    if event_type == "option_iv_change":
        return "期权波动"
    return "市场新闻"


def _direction_bias(text: str, event_type: str) -> tuple[str, float, float]:
    bullish = _count_terms(text, BULLISH_TERMS)
    bearish = _count_terms(text, BEARISH_TERMS)
    vol = _count_terms(text, VOLATILITY_TERMS)
    if bullish > bearish:
        confidence = min(1.0, 0.36 + 0.18 * bullish + 0.04 * vol)
        return "bullish", confidence, min(1.0, (bullish - bearish) / 4.0)
    if bearish > bullish:
        confidence = min(1.0, 0.36 + 0.18 * bearish + 0.04 * vol)
        return "bearish", confidence, -min(1.0, (bearish - bullish) / 4.0)
    if vol > 0 or event_type in {"margin_change", "exchange_notice"}:
        return "volatility", min(1.0, 0.42 + 0.12 * vol), 0.0
    return "neutral", 0.25, 0.0


def _relevance(text: str) -> float:
    score = 0.0
    if _contains_any(text, TIN_TERMS):
        score += 0.52
    if _contains_any(text, SUPPLY_TERMS):
        score += 0.20
    if _contains_any(text, DEMAND_TERMS):
        score += 0.12
    if _contains_any(text, INVENTORY_TERMS):
        score += 0.12
    if _contains_any(text, EXCHANGE_TERMS):
        score += 0.16
    if _contains_any(text, MACRO_TERMS):
        score += 0.08
    return min(score, 1.0)


def _impact(text: str, event_type: str, relevance: float, tier: str) -> float:
    base = 0.12 + relevance * 0.56
    if event_type in {"supply_disruption", "warehouse_receipt_change", "inventory_change", "margin_change", "macro_policy"}:
        base += 0.14
    if _contains_any(text, {"重大", "突发", "停产", "禁令", "大幅", "大增", "大降", "加息", "降息", "国庆", "春节", "high", "major"}):
        base += 0.12
    if tier == "tier1":
        base += 0.08
    return max(0.0, min(1.0, base))


def _decay_weight(available_at: pd.Timestamp | None, *, now: pd.Timestamp | None = None) -> float:
    if available_at is None:
        return 0.0
    now = now or pd.Timestamp.now(tz="Asia/Hong_Kong")
    hours = max(0.0, (now - available_at).total_seconds() / 3600.0)
    return float(max(0.06, min(1.0, math.exp(-hours / 168.0))))


def event_id_for(title: str, source: str, published_at: str, url: str) -> str:
    domain = urlparse(url).netloc.lower()
    bucket = str(published_at or "")[:13]
    normalized = " ".join(str(title or "").lower().split())
    return hashlib.sha256(f"{normalized}|{source}|{bucket}|{domain}".encode("utf-8")).hexdigest()[:24]


def build_event_from_article(article: Mapping[str, Any], *, batch_id: str = "") -> dict[str, Any] | None:
    title = str(article.get("title") or article.get("summary") or "").strip()
    if not title:
        return None
    summary = str(article.get("summary") or article.get("description") or article.get("content") or title).strip()
    raw_text = str(article.get("raw_text") or article.get("content") or summary or title)
    text = f"{title} {summary} {raw_text}"
    source = _source(article)
    provider = _provider(article)
    raw_url = str(article.get("raw_url") or article.get("url") or article.get("source_url") or article.get("canonical_url") or "")
    resolved_url = resolve_canonical_url(str(article.get("canonical_url") or raw_url), network=False)
    url = resolved_url.canonical_url or safe_url(raw_url)
    published = _published_at(article)
    now = pd.Timestamp.now(tz="Asia/Hong_Kong")
    available_text = str(article.get("available_at") or article.get("fetched_at") or now.isoformat())
    available_ts = parse_time(available_text)
    event_time_confidence = _event_time_confidence(published)
    tier = source_tier(provider, source)
    relevance = _relevance(text)
    provider_lower = provider.lower()
    url_lower = url.lower()
    if relevance < 0.18 and (
        any(key in provider_lower for key in ("shfe", "shmet", "smm", "mysteel", "tin", "有色", "期货"))
        or any(key in url_lower for key in ("sn", "tin", "shfe", "shmet", "smm"))
    ):
        relevance = 0.22
    event_type = _event_type(text)
    direction, direction_confidence, sentiment = _direction_bias(text, event_type)
    impact = max(float(article.get("impact_score") or 0.0), _impact(text, event_type, relevance, tier))
    if impact > 1.0:
        impact = impact / 100.0
    decay = _decay_weight(available_ts, now=now)
    source_conf = source_tier_weight(tier)
    final_weight = float(max(0.0, min(1.0, source_conf * impact * max(direction_confidence, 0.18) * decay)))
    symbol_tags = ["SN", "沪锡", "锡"] if relevance >= 0.18 else []
    entity_tags = []
    for term in ("缅甸", "佤邦", "印尼", "LME", "上期所", "半导体", "光伏", "仓单", "库存", "美联储", "美元", "国庆", "春节", "海关"):
        if term.lower() in text.lower():
            entity_tags.append(term)
    return {
        "event_id": str(article.get("event_id") or event_id_for(title, source, published, url)),
        "title": title[:300],
        "summary": summary[:1200],
        "raw_text": raw_text[:4000],
        "source": source,
        "source_tier": tier,
        "provider": provider,
        "canonical_url": url,
        "raw_url": raw_url,
        "url_status": resolved_url.url_status,
        "url_sanitized": url,
        "region": _region(article, provider, source, url),
        "language": _language(article, text),
        "published_at": published,
        "source_published_at": published,
        "fetched_at": str(article.get("fetched_at") or now.isoformat()),
        "available_at": available_text if available_ts is not None else "",
        "event_time_confidence": round(event_time_confidence, 5),
        "updated_at": now.isoformat(),
        "category": _category(event_type),
        "event_type": event_type,
        "entity_tags": entity_tags,
        "symbol_tags": symbol_tags,
        "commodity_tags": ["tin", "SN"] if symbol_tags else [],
        "horizon_tags": [],
        "direction_bias": direction,
        "direction_confidence": round(direction_confidence, 5),
        "impact_score": round(impact, 5),
        "sentiment_score": round(float(article.get("sentiment_score", sentiment) or sentiment), 5),
        "supply_score": round(impact if event_type in {"supply_disruption", "smelter_output_change", "import_export"} else 0.0, 5),
        "demand_score": round(impact if event_type == "downstream_demand" else 0.0, 5),
        "inventory_score": round(impact if event_type in {"inventory_change", "warehouse_receipt_change"} else 0.0, 5),
        "policy_score": round(impact if event_type in {"exchange_notice", "margin_change", "macro_policy"} else 0.0, 5),
        "macro_score": round(impact if event_type == "macro_policy" else 0.0, 5),
        "volatility_score": round(impact if direction == "volatility" or event_type in {"margin_change", "exchange_notice"} else 0.0, 5),
        "risk_score": round(impact if direction in {"volatility", "mixed"} else 0.0, 5),
        "time_decay_weight": round(decay, 5),
        "source_confidence": round(source_conf, 5),
        "source_reliability_score": round(source_conf, 5),
        "final_event_weight": round(final_weight, 5),
        "used_in_model": 0,
        "rejected_reason": "",
        "feature_window": "",
        "content_hash": hashlib.sha256(f"{title}|{summary}|{url}".encode("utf-8")).hexdigest(),
        "dedupe_key": hashlib.sha256(f"{title.lower()}|{urlparse(url).netloc.lower()}|{published[:10]}".encode("utf-8")).hexdigest()[:24],
        "event_group_id": hashlib.sha256(f"{event_type}|{title.lower()[:80]}|{published[:10]}".encode("utf-8")).hexdigest()[:16],
        "batch_id": batch_id,
        "relevance_score": round(relevance, 5),
    }
