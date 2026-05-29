from __future__ import annotations

import math
import re
from dataclasses import dataclass, asdict
from typing import Any

import numpy as np
import pandas as pd

from .forecast_math import cohere_directional_forecast
from .price_risk import apply_realistic_price_gate, get_horizon_spec
from .trading_calendar import next_sn_trading_window

POSITIVE_TERMS = {
    "tight supply": 0.45,
    "output cut": 0.50,
    "shutdown": 0.55,
    "strike": 0.40,
    "inventory draw": 0.35,
    "policy support": 0.28,
    "stimulus": 0.22,
    "solar demand": 0.24,
    "semiconductor recovery": 0.22,
    "mine disruption": 0.48,
    "ore shortage": 0.44,
}

NEGATIVE_TERMS = {
    "demand slowdown": -0.40,
    "inventory build": -0.34,
    "rate hike": -0.28,
    "hawkish": -0.26,
    "recession": -0.34,
    "supply recovery": -0.18,
    "maintenance end": -0.20,
    "export resumption": -0.22,
    "tariff": -0.18,
    "weak electronics": -0.24,
}

DIMENSION_TERMS = {
    "supply": {"mine", "smelter", "ore", "inventory", "warehouse", "export", "import", "maintenance", "shutdown", "strike"},
    "demand": {"solar", "pv", "semiconductor", "electronics", "solder", "consumption", "orders", "demand", "export"},
    "macro": {"fed", "rate", "yield", "dollar", "fx", "macro", "gdp", "inflation", "pmi", "liquidity"},
    "policy": {"policy", "tax", "tariff", "quota", "regulation", "subsidy", "industry", "support"},
}

SEVERITY_TERMS = {
    "major": {"emergency", "halt", "ban", "strike", "shutdown", "sanction", "collapse"},
    "medium": {"tight", "cut", "warning", "slowdown", "maintenance", "delay"},
}


@dataclass(frozen=True)
class TextFeatureSummary:
    article_count: int
    dominant_dimension: str
    sentiment_mean: float
    impact_mean: float
    sentiment_trend_3: float
    severe_event_probability: float
    bullish_ratio: float
    bearish_ratio: float
    topic_heat_score: float
    news_consensus: float
    hot_topics: tuple[str, ...]
    top_headlines: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _normalize_text(*parts: str) -> str:
    text = " ".join(part or "" for part in parts)
    text = re.sub(r"\s+", " ", text.lower())
    return text.strip()


def _term_score(text: str, lexicon: dict[str, float]) -> float:
    score = 0.0
    for phrase, weight in lexicon.items():
        if phrase in text:
            score += weight
    return score


def _dimension(text: str) -> str:
    counts: dict[str, int] = {}
    tokens = set(re.findall(r"[a-z]{2,}", text))
    for name, keywords in DIMENSION_TERMS.items():
        counts[name] = len(tokens.intersection(keywords))
    return max(counts, key=counts.get) if any(counts.values()) else "macro"


def _severity(text: str) -> str:
    tokens = set(re.findall(r"[a-z]{2,}", text))
    if tokens.intersection(SEVERITY_TERMS["major"]):
        return "major"
    if tokens.intersection(SEVERITY_TERMS["medium"]):
        return "medium"
    return "minor"


def _impact_level(score: float, severity: str) -> str:
    base = abs(score)
    if severity == "major" or base >= 0.45:
        return "major"
    if severity == "medium" or base >= 0.22:
        return "general"
    return "minor"


def _hot_topics(article_frame: pd.DataFrame, limit: int = 6) -> tuple[str, ...]:
    if article_frame.empty:
        return ()
    stop_words = {
        "the", "and", "for", "with", "from", "that", "this", "into", "over", "under", "after",
        "market", "markets", "price", "prices", "said", "says", "news", "latest", "update",
        "china", "global", "will", "may", "are", "was", "were", "has", "have", "tin",
    }
    weighted: dict[str, float] = {}
    for _, row in article_frame.iterrows():
        text = _normalize_text(str(row.get("title", "")), str(row.get("description", "")))
        tokens = re.findall(r"[a-z][a-z\-]{2,}", text)
        impact = float(row.get("impact_score", 0.0) or 0.0)
        sentiment = abs(float(row.get("sentiment_score", 0.0) or 0.0))
        weight = 1.0 + impact + sentiment
        for token in tokens:
            token = token.strip("-")
            if token in stop_words or len(token) < 4:
                continue
            weighted[token] = weighted.get(token, 0.0) + weight
    return tuple(key for key, _ in sorted(weighted.items(), key=lambda item: item[1], reverse=True)[:limit])


def _parse_timestamp(value: Any) -> pd.Timestamp | pd.NaT:
    if value in (None, ""):
        return pd.NaT
    return pd.to_datetime(value, errors="coerce", utc=True)


def article_feature_frame(articles: list[dict[str, Any]] | None) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for article in articles or []:
        title = str(article.get("title", "") or "")
        description = str(article.get("description", "") or "")
        source = article.get("source", {})
        source_name = source.get("name") if isinstance(source, dict) else article.get("source_name", "")
        text = _normalize_text(title, description, str(article.get("content", "") or ""))
        if not text:
            continue
        sentiment = float(np.clip(_term_score(text, POSITIVE_TERMS) + _term_score(text, NEGATIVE_TERMS), -1.0, 1.0))
        dimension = _dimension(text)
        severity = _severity(text)
        impact = float(np.clip(abs(sentiment) + {"minor": 0.10, "medium": 0.24, "major": 0.40}[severity], 0.0, 1.0))
        published_at = _parse_timestamp(article.get("publishedAt") or article.get("published_at"))
        rows.append(
            {
                "published_at": published_at,
                "source": str(source_name or "unknown"),
                "title": title,
                "description": description,
                "dimension": dimension,
                "severity": severity,
                "impact_level": _impact_level(sentiment, severity),
                "sentiment_score": sentiment,
                "impact_score": impact,
                "url": str(article.get("url", "") or ""),
            }
        )
    frame = pd.DataFrame(rows)
    if frame.empty:
        return frame
    frame = frame.sort_values("published_at", ascending=False).reset_index(drop=True)
    return frame


def summarize_articles(article_frame: pd.DataFrame) -> TextFeatureSummary:
    if article_frame.empty:
        return TextFeatureSummary(
            article_count=0,
            dominant_dimension="macro",
            sentiment_mean=0.0,
            impact_mean=0.0,
            sentiment_trend_3=0.0,
            severe_event_probability=0.0,
            bullish_ratio=0.0,
            bearish_ratio=0.0,
            topic_heat_score=0.0,
            news_consensus=0.0,
            hot_topics=(),
            top_headlines=(),
        )

    dominant_dimension = (
        article_frame["dimension"].value_counts().idxmax()
        if not article_frame["dimension"].empty
        else "macro"
    )
    recent = article_frame.head(3)
    sentiment_mean = float(article_frame["sentiment_score"].mean())
    impact_mean = float(article_frame["impact_score"].mean())
    sentiment_trend_3 = float(recent["sentiment_score"].mean()) if not recent.empty else 0.0
    severe_event_probability = float((article_frame["impact_level"] == "major").mean())
    bullish_ratio = float((article_frame["sentiment_score"] > 0.15).mean())
    bearish_ratio = float((article_frame["sentiment_score"] < -0.15).mean())
    topic_heat_score = float(np.clip(np.log1p(len(article_frame)) / np.log(21) * impact_mean, 0.0, 1.0))
    news_consensus = float(np.clip(abs(bullish_ratio - bearish_ratio), 0.0, 1.0))
    hot_topics = _hot_topics(article_frame)
    top_headlines = tuple(article_frame["title"].head(3).tolist())
    return TextFeatureSummary(
        article_count=int(len(article_frame)),
        dominant_dimension=str(dominant_dimension),
        sentiment_mean=sentiment_mean,
        impact_mean=impact_mean,
        sentiment_trend_3=sentiment_trend_3,
        severe_event_probability=severe_event_probability,
        bullish_ratio=bullish_ratio,
        bearish_ratio=bearish_ratio,
        topic_heat_score=topic_heat_score,
        news_consensus=news_consensus,
        hot_topics=hot_topics,
        top_headlines=top_headlines,
    )


def build_historical_event_matches(
    raw: pd.DataFrame,
    article_summary: TextFeatureSummary,
    limit: int = 3,
) -> list[dict[str, Any]]:
    if raw.empty:
        return []

    event_days = raw.copy()
    event_days = event_days[event_days["event_flag"].fillna(0).astype(int) == 1]
    if event_days.empty:
        event_days = raw.tail(20)

    direction = np.sign(article_summary.sentiment_mean) or 1.0
    target_vector = np.array(
        [
            article_summary.impact_mean,
            article_summary.severe_event_probability,
            abs(article_summary.sentiment_trend_3),
            float(direction > 0),
        ],
        dtype=float,
    )

    scored: list[dict[str, Any]] = []
    for idx, row in event_days.iterrows():
        sample_vector = np.array(
            [
                min(abs(float(row.get("event_score", 0.0))) / 3.0, 1.0),
                float(abs(float(row.get("event_score", 0.0))) > 1.5),
                min(abs(float(row.get("sentiment_score", 0.0))), 1.0),
                float(float(row.get("sentiment_score", 0.0)) > 0),
            ],
            dtype=float,
        )
        distance = float(np.linalg.norm(target_vector - sample_vector))
        similarity = float(np.clip(1.0 - distance / math.sqrt(len(target_vector)), 0.0, 1.0))
        future_5d = float(raw["close"].shift(-5).get(idx, np.nan) / max(float(row["close"]), 1.0) - 1.0) if idx in raw.index else np.nan
        future_20d = float(raw["close"].shift(-20).get(idx, np.nan) / max(float(row["close"]), 1.0) - 1.0) if idx in raw.index else np.nan
        scored.append(
            {
                "date": str(idx.date()),
                "similarity": similarity,
                "event_score": float(row.get("event_score", 0.0)),
                "sentiment_score": float(row.get("sentiment_score", 0.0)),
                "future_5d_return": future_5d,
                "future_20d_return": future_20d,
            }
        )

    scored.sort(key=lambda item: item["similarity"], reverse=True)
    return scored[:limit]


def multimodal_adjustment(
    predictions: pd.DataFrame,
    article_summary: TextFeatureSummary | dict[str, Any],
) -> pd.DataFrame:
    if predictions.empty:
        return predictions.copy()

    if isinstance(article_summary, dict):
        article_summary = TextFeatureSummary(
            article_count=int(article_summary.get("article_count", 0) or 0),
            dominant_dimension=str(article_summary.get("dominant_dimension", "macro") or "macro"),
            sentiment_mean=float(article_summary.get("sentiment_mean", 0.0) or 0.0),
            impact_mean=float(article_summary.get("impact_mean", 0.0) or 0.0),
            sentiment_trend_3=float(article_summary.get("sentiment_trend_3", 0.0) or 0.0),
            severe_event_probability=float(article_summary.get("severe_event_probability", 0.0) or 0.0),
            bullish_ratio=float(article_summary.get("bullish_ratio", 0.0) or 0.0),
            bearish_ratio=float(article_summary.get("bearish_ratio", 0.0) or 0.0),
            topic_heat_score=float(article_summary.get("topic_heat_score", 0.0) or 0.0),
            news_consensus=float(article_summary.get("news_consensus", 0.0) or 0.0),
            hot_topics=tuple(article_summary.get("hot_topics", ()) or ()),
            top_headlines=tuple(article_summary.get("top_headlines", ()) or ()),
        )

    work = predictions.copy()
    hotspot_bias = 0.04 * article_summary.news_consensus * np.sign(article_summary.sentiment_mean)
    bias = 0.15 * article_summary.sentiment_mean + 0.10 * (article_summary.bullish_ratio - article_summary.bearish_ratio) + hotspot_bias
    confidence_boost = 8.0 * article_summary.impact_mean * (1.0 - article_summary.severe_event_probability * 0.35) + 4.0 * article_summary.topic_heat_score
    work["text_sentiment_bias"] = bias
    work["text_impact_score"] = article_summary.impact_mean
    work["text_topic_heat"] = article_summary.topic_heat_score
    work["text_news_consensus"] = article_summary.news_consensus
    work["prob_up_multimodal"] = np.clip(work["prob_up"] + bias, 0.01, 0.99)
    work["confidence_multimodal"] = np.clip(work["confidence"] + confidence_boost, 0.0, 100.0)
    return work


def _coerce_summary(summary: TextFeatureSummary | dict[str, Any] | None) -> TextFeatureSummary:
    if isinstance(summary, TextFeatureSummary):
        return summary
    summary = summary or {}
    return TextFeatureSummary(
        article_count=int(summary.get("article_count", 0) or 0),
        dominant_dimension=str(summary.get("dominant_dimension", "macro") or "macro"),
        sentiment_mean=float(summary.get("sentiment_mean", 0.0) or 0.0),
        impact_mean=float(summary.get("impact_mean", 0.0) or 0.0),
        sentiment_trend_3=float(summary.get("sentiment_trend_3", 0.0) or 0.0),
        severe_event_probability=float(summary.get("severe_event_probability", 0.0) or 0.0),
        bullish_ratio=float(summary.get("bullish_ratio", 0.0) or 0.0),
        bearish_ratio=float(summary.get("bearish_ratio", 0.0) or 0.0),
        topic_heat_score=float(summary.get("topic_heat_score", 0.0) or 0.0),
        news_consensus=float(summary.get("news_consensus", 0.0) or 0.0),
        hot_topics=tuple(summary.get("hot_topics", ()) or ()),
        top_headlines=tuple(summary.get("top_headlines", ()) or ()),
    )


def _driver_lines(latest_pred: pd.Series, text_summary: TextFeatureSummary) -> list[str]:
    drivers = [part.strip() for part in str(latest_pred.get("driver_summary", "")).split(";") if part.strip()]
    policy_action = str(latest_pred.get("bandit_action_label", "") or "")
    if policy_action:
        drivers.append(f"策略自适应:{policy_action}")
    if text_summary.top_headlines:
        drivers.append(f"新闻:{text_summary.top_headlines[0]}")
    if text_summary.hot_topics:
        drivers.append("热点:" + "/".join(text_summary.hot_topics[:4]))
    if text_summary.dominant_dimension:
        drivers.append(f"文本主导:{text_summary.dominant_dimension}")
    return drivers[:5]


def _direction_label(prob_up: float) -> str:
    if prob_up >= 0.60:
        return "偏多"
    if prob_up <= 0.40:
        return "偏空"
    return "中性"


def _forecast_payload(
    *,
    horizon_key: str,
    horizon_label: str,
    anchor_time: str,
    generated_at: str,
    target_label: str,
    target_start: str,
    target_end: str,
    close: float,
    expected_return: float,
    prob_up: float,
    confidence: float,
    volatility: float,
    core_drivers: list[str],
    historical_matches: list[dict[str, Any]] | None = None,
    scenario_note: str = "",
    contract_code: str | None = None,
) -> dict[str, Any]:
    raw_expected_return = _safe_float(expected_return, 0.0)
    raw_prob_up = _safe_float(prob_up, 0.5)
    volatility = max(_safe_float(volatility, 0.01), 1e-4)
    close = max(_safe_float(close, 0.0), 0.0)
    expected_return, prob_up = cohere_directional_forecast(raw_expected_return, raw_prob_up, volatility)
    spec = get_horizon_spec(horizon_key)
    return_cap = spec.max_center_offset
    clipped_return = float(np.clip(expected_return, -return_cap, return_cap))
    if abs(clipped_return - expected_return) > 1e-9:
        expected_return = clipped_return
        implied_after_clip = 0.5 + 0.5 * float(np.tanh(expected_return / max(volatility * 1.35, 1e-4)))
        prob_up = float(np.clip(0.55 * prob_up + 0.45 * implied_after_clip, 0.02, 0.98))
    implied_prob_from_return = 0.5 + 0.5 * float(np.tanh(raw_expected_return / max(volatility * 1.35, 1e-4)))
    consistency_gap = abs((raw_prob_up - 0.5) - (implied_prob_from_return - 0.5))
    consistency_penalty = min(consistency_gap * 18.0, 10.0)
    confidence = float(np.clip(confidence - consistency_penalty, 5.0, 99.0))
    band_multiplier = 1.18 if abs(prob_up - 0.5) >= 0.18 else 1.42
    range_low = max(0.0, close * (1.0 + expected_return - band_multiplier * volatility))
    range_high = max(range_low, close * (1.0 + expected_return + band_multiplier * volatility))
    center = close * (1.0 + expected_return)
    detail = {
        "horizon_key": horizon_key,
        "horizon_label": horizon_label,
        "anchor_time": anchor_time,
        "generated_at": generated_at,
        "target_label": target_label,
        "target_start": target_start,
        "target_end": target_end,
        "anchor_close": close,
        "expected_return": expected_return,
        "volatility": volatility,
        "price_center": center,
        "range_low": range_low,
        "range_high": range_high,
        "prob_up": prob_up,
        "prob_down": 1.0 - prob_up,
        "confidence": confidence,
        "raw_expected_return": raw_expected_return,
        "raw_prob_up": raw_prob_up,
        "consistency_gap": consistency_gap,
        "calibration_quality_score": float(np.clip(100.0 - consistency_gap * 160.0, 0.0, 100.0)),
        "direction_key": _direction_key(prob_up),
        "direction_label": _direction_label_zh(prob_up),
        "contract_code": contract_code or "",
        "core_drivers": core_drivers,
        "historical_matches": historical_matches or [],
        "scenario_note": scenario_note,
    }
    return apply_realistic_price_gate(detail)


def _forecast_clock(raw: pd.DataFrame, live_snapshot: dict[str, Any] | None = None) -> tuple[pd.Timestamp, pd.Timestamp]:
    generated = pd.to_datetime((live_snapshot or {}).get("generated_at"), errors="coerce")
    if pd.isna(generated):
        generated = pd.Timestamp.now(tz="Asia/Hong_Kong")
    elif generated.tzinfo is None:
        generated = generated.tz_localize("Asia/Hong_Kong")
    else:
        generated = generated.tz_convert("Asia/Hong_Kong")

    market_anchor = pd.Timestamp(raw.index[-1])
    if market_anchor.tzinfo is None:
        market_anchor = market_anchor.tz_localize("Asia/Hong_Kong")
    else:
        market_anchor = market_anchor.tz_convert("Asia/Hong_Kong")
    return generated, market_anchor


def _session_ts(base_day: pd.Timestamp, hour: int, minute: int = 0) -> pd.Timestamp:
    naive_day = base_day.tz_localize(None).normalize()
    return (naive_day + pd.Timedelta(hours=hour, minutes=minute)).tz_localize("Asia/Hong_Kong")


def _next_business_day_start(current: pd.Timestamp, hour: int = 9, minute: int = 0) -> pd.Timestamp:
    next_day = current.tz_localize(None).normalize() + pd.offsets.BDay(1)
    return (next_day + pd.Timedelta(hours=hour, minutes=minute)).tz_localize("Asia/Hong_Kong")


def _next_shfe_trading_window(current: pd.Timestamp) -> tuple[pd.Timestamp, pd.Timestamp]:
    start, end, _state = next_sn_trading_window(current)
    return start, end


def _contract_code(live_snapshot: dict[str, Any] | None = None) -> str:
    meta = (live_snapshot or {}).get("contract_meta", {})
    if isinstance(meta, dict):
        return str(meta.get("active_contract", "") or meta.get("target_contract", "") or "")
    return ""


def _latest_horizon_row(
    horizon_predictions: dict[str, pd.DataFrame] | None,
    horizon_name: str,
    fallback: pd.Series,
) -> pd.Series:
    if isinstance(horizon_predictions, dict):
        frame = horizon_predictions.get(horizon_name)
        if isinstance(frame, pd.DataFrame) and not frame.empty:
            return frame.iloc[-1]
    return fallback


def _direction_label_zh(prob_up: float) -> str:
    if prob_up >= 0.60:
        return "偏多"
    if prob_up <= 0.40:
        return "偏空"
    return "中性"


def _direction_key(prob_up: float) -> str:
    if prob_up >= 0.60:
        return "bullish"
    if prob_up <= 0.40:
        return "bearish"
    return "neutral"


def _has_horizon_frame(horizon_predictions: dict[str, pd.DataFrame] | None, horizon_name: str) -> bool:
    if not isinstance(horizon_predictions, dict):
        return False
    frame = horizon_predictions.get(horizon_name)
    return isinstance(frame, pd.DataFrame) and not frame.empty


def _trend_return(raw: pd.DataFrame, lookback: int) -> float:
    if len(raw) <= lookback:
        return 0.0
    anchor = float(raw["close"].iloc[-lookback - 1])
    if anchor == 0:
        return 0.0
    return float(raw["close"].iloc[-1] / anchor - 1.0)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except Exception:
        return default
    if math.isnan(parsed) or math.isinf(parsed):
        return default
    return parsed


def _json_sanitize(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _json_sanitize(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_json_sanitize(item) for item in value)
    if isinstance(value, (np.floating, float)):
        numeric = float(value)
        return numeric if math.isfinite(numeric) else None
    if isinstance(value, (np.integer, int)):
        return int(value)
    return value


def _scaled_horizon_return(
    *,
    base_return: float,
    horizon_days: int,
    trend_return: float,
    regime: str,
    text_bias: float,
    extra_bias: float,
    cap: float,
) -> float:
    regime_bias = {
        "UPTREND": 0.010,
        "DOWNTREND": -0.010,
        "WIDE_RANGE": 0.000,
        "NARROW_RANGE": 0.002,
    }.get(str(regime), 0.0)
    compounded = float(np.expm1(np.clip(base_return * max(np.sqrt(max(horizon_days, 1)), 1.0), -0.12, 0.12)))
    blended = 0.36 * compounded + 0.34 * trend_return + 0.65 * regime_bias + text_bias + extra_bias
    return float(np.clip(blended, -cap, cap))


def _probability_from_expected_return(expected_return: float, volatility: float, base_prob: float) -> float:
    scaled_edge = float(np.tanh(expected_return / max(volatility * 1.35, 1e-4)))
    implied_prob = 0.5 + 0.5 * scaled_edge
    return float(np.clip(0.52 * base_prob + 0.48 * implied_prob, 0.03, 0.97))


SHORT_HORIZON_CONFIG: dict[str, dict[str, Any]] = {
    "next_5m": {"label": "未来5分钟", "minutes": 5, "min_ticks": 4, "edge_floor": 0.0009, "vol_floor": 0.0006},
    "next_15m": {"label": "未来15分钟", "minutes": 15, "min_ticks": 5, "edge_floor": 0.0014, "vol_floor": 0.0010},
    "next_30m": {"label": "未来30分钟", "minutes": 30, "min_ticks": 6, "edge_floor": 0.0020, "vol_floor": 0.0015},
}


def _recent_tick_frame(live_snapshot: dict[str, Any] | None) -> pd.DataFrame:
    rows = (live_snapshot or {}).get("recent_ticks", [])
    if not isinstance(rows, list) or not rows:
        return pd.DataFrame()
    frame = pd.DataFrame([row for row in rows if isinstance(row, dict)])
    if frame.empty or "latest" not in frame.columns:
        return pd.DataFrame()
    frame["ts"] = pd.to_datetime(frame.get("ts"), errors="coerce")
    frame["latest"] = pd.to_numeric(frame.get("latest"), errors="coerce")
    for column in ("volume", "open_interest"):
        if column in frame.columns:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["ts", "latest"]).sort_values("ts").reset_index(drop=True)
    return frame


def _short_horizon_components(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    live_snapshot: dict[str, Any] | None,
    *,
    minutes: int,
    edge_floor: float,
    vol_floor: float,
) -> dict[str, Any]:
    latest_pred = predictions.iloc[-1]
    text_summary = _coerce_summary((live_snapshot or {}).get("text_summary"))
    ticks = _recent_tick_frame(live_snapshot)
    base_return = _safe_float(latest_pred.get("predicted_return", 0.0), 0.0)
    daily_vol = max(_safe_float(latest_pred.get("ewma_vol_20", 0.18), 0.18) / np.sqrt(252), 0.006)
    expected_return = base_return * (minutes / 240.0) + 0.035 * text_summary.sentiment_trend_3
    volatility = max(daily_vol * np.sqrt(minutes / 240.0), vol_floor)
    tick_count = int(len(ticks))
    coverage_minutes = 0.0
    source = "短线参考兜底"
    eligible = False
    gate_hint = "分钟线/实时快照不足，短线预测仅作为参考，不纳入命中率。"

    if tick_count >= 2:
        first_ts = pd.Timestamp(ticks["ts"].iloc[0])
        last_ts = pd.Timestamp(ticks["ts"].iloc[-1])
        coverage_minutes = max((last_ts - first_ts).total_seconds() / 60.0, 0.0)
        prices = ticks["latest"].astype(float)
        tick_return = float(prices.iloc[-1] / max(prices.iloc[0], 1e-9) - 1.0)
        tick_vol = float(prices.pct_change().dropna().std() or 0.0) * np.sqrt(max(tick_count, 2))
        vol_momentum = 0.0
        oi_momentum = 0.0
        if "volume" in ticks.columns and ticks["volume"].notna().sum() >= 2:
            vol_momentum = float(np.tanh((ticks["volume"].iloc[-1] - ticks["volume"].iloc[0]) / max(abs(ticks["volume"].iloc[0]), 1.0))) * 0.0008
        if "open_interest" in ticks.columns and ticks["open_interest"].notna().sum() >= 2:
            oi_momentum = float(np.tanh((ticks["open_interest"].iloc[-1] - ticks["open_interest"].iloc[0]) / max(abs(ticks["open_interest"].iloc[0]), 1.0))) * 0.0008
        expected_return = 0.62 * tick_return + 0.22 * expected_return + vol_momentum + oi_momentum
        volatility = max(tick_vol * np.sqrt(max(minutes, 1) / max(coverage_minutes, 1.0)), volatility, vol_floor)
        eligible = tick_count >= max(3, int(minutes / 5) + 2) and coverage_minutes >= max(1.0, minutes * 0.35)
        source = "实时快照聚合" if eligible else "实时快照不足覆盖"
        gate_hint = f"实时快照覆盖约{coverage_minutes:.1f}分钟，样本{tick_count}个。"

    if not eligible:
        expected_return *= 0.45
        volatility = max(volatility, vol_floor * 1.25)
    if abs(expected_return) < edge_floor:
        expected_return *= 0.35
    base_prob = _safe_float(latest_pred.get("prob_up_multimodal", latest_pred.get("prob_up", 0.5)), 0.5)
    prob_up = _probability_from_expected_return(expected_return, volatility, base_prob)
    if not eligible:
        prob_up = float(np.clip(0.5 + (prob_up - 0.5) * 0.45, 0.35, 0.65))
    confidence = float(
        np.clip(
            _safe_float(latest_pred.get("confidence_multimodal", latest_pred.get("confidence", 50.0)), 50.0)
            - (10 if not eligible else 3)
            + 8 * min(coverage_minutes / max(minutes, 1), 1.0)
            + 5 * min(text_summary.impact_mean, 1.0),
            5,
            92,
        )
    )
    return {
        "expected_return": expected_return,
        "prob_up": prob_up,
        "confidence": confidence,
        "volatility": volatility,
        "micro_data_source": source,
        "validation_eligible": eligible,
        "validation_note": gate_hint if eligible else "分钟线/实时快照不足，短线预测仅供参考，不纳入真实短线验证。",
        "tick_count": tick_count,
        "coverage_minutes": coverage_minutes,
    }


def predict_next_minutes(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    live_snapshot: dict[str, Any] | None = None,
    *,
    horizon_key: str,
) -> dict[str, Any]:
    config = SHORT_HORIZON_CONFIG[horizon_key]
    minutes = int(config["minutes"])
    latest_raw = raw.iloc[-1]
    latest_pred = predictions.iloc[-1]
    text_summary = _coerce_summary((live_snapshot or {}).get("text_summary"))
    generated, market_anchor = _forecast_clock(raw, live_snapshot)
    target_start, target_end, trading_state = next_sn_trading_window(generated, minutes=minutes)
    components = _short_horizon_components(
        raw,
        predictions,
        live_snapshot,
        minutes=minutes,
        edge_floor=float(config["edge_floor"]),
        vol_floor=float(config["vol_floor"]),
    )
    payload = _forecast_payload(
        horizon_key=horizon_key,
        horizon_label=str(config["label"]),
        anchor_time=f"market anchor {market_anchor.strftime('%Y-%m-%d %H:%M %Z')}",
        generated_at=generated.strftime("%Y-%m-%d %H:%M %Z"),
        target_label=f"{target_start.strftime('%Y-%m-%d %H:%M')} to {target_end.strftime('%H:%M %Z')}",
        target_start=target_start.strftime("%Y-%m-%d %H:%M %Z"),
        target_end=target_end.strftime("%Y-%m-%d %H:%M %Z"),
        close=float(latest_raw["close"]),
        expected_return=float(components["expected_return"]),
        prob_up=float(components["prob_up"]),
        confidence=float(components["confidence"]),
        volatility=float(components["volatility"]),
        core_drivers=_driver_lines(latest_pred, text_summary),
        historical_matches=(live_snapshot or {}).get("historical_matches", []),
        scenario_note="短周期预测采用实时价锚定、快照量价动量和突发新闻弱因子；数据不足时仅作参考。",
        contract_code=_contract_code(live_snapshot),
    )
    normal_low = float(payload.get("range_low", payload.get("price_center", float(latest_raw["close"]))))
    normal_high = float(payload.get("range_high", payload.get("price_center", float(latest_raw["close"]))))
    center = float(payload.get("price_center", float(latest_raw["close"])))
    payload["trading_window"] = trading_state
    payload["window_minutes"] = minutes
    payload["micro_data_source"] = components["micro_data_source"]
    payload["validation_eligible"] = bool(components["validation_eligible"])
    payload["validation_note"] = str(components["validation_note"])
    payload["normal_range"] = {"low": normal_low, "high": normal_high}
    payload["risk_extended_range"] = {
        "low": max(0.0, center - 1.6 * abs(center - normal_low)),
        "high": center + 1.6 * abs(normal_high - center),
    }
    payload["microstructure"] = {
        "tick_count": int(components["tick_count"]),
        "coverage_minutes": float(components["coverage_minutes"]),
        "source": components["micro_data_source"],
    }
    return payload


def predict_next_hour(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    live_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    latest_raw = raw.iloc[-1]
    latest_pred = predictions.iloc[-1]
    text_summary = _coerce_summary((live_snapshot or {}).get("text_summary"))
    generated, market_anchor = _forecast_clock(raw, live_snapshot)
    target_start, target_end, trading_state = next_sn_trading_window(generated)
    hourly_vol = max(float(latest_pred.get("ewma_vol_20", 0.18)) / np.sqrt(252 * 6), 0.0025)
    expected_return = (
        0.22 * _safe_float(latest_pred.get("predicted_return", 0.0), 0.0)
        + 0.35 * text_summary.sentiment_trend_3
        + 0.20 * _safe_float(latest_raw.get("lme_overnight_return", 0.0), 0.0)
        + 0.10 * _safe_float(latest_raw.get("domestic_open_gap", 0.0), 0.0)
    )
    prob_up = float(np.clip(_safe_float(latest_pred.get("prob_up_multimodal", latest_pred.get("prob_up", 0.5)), 0.5) + 0.18 * text_summary.sentiment_trend_3, 0.01, 0.99))
    confidence = float(np.clip(_safe_float(latest_pred.get("confidence_multimodal", latest_pred.get("confidence", 50.0)), 50.0) - 6 + 10 * text_summary.impact_mean, 5, 99))
    payload = _forecast_payload(
        horizon_key="next_hour",
        horizon_label="下一小时",
        anchor_time=f"market anchor {market_anchor.strftime('%Y-%m-%d %H:%M %Z')}",
        generated_at=generated.strftime("%Y-%m-%d %H:%M %Z"),
        target_label=f"{target_start.strftime('%Y-%m-%d %H:%M')} to {target_end.strftime('%H:%M %Z')}",
        target_start=target_start.strftime("%Y-%m-%d %H:%M %Z"),
        target_end=target_end.strftime("%Y-%m-%d %H:%M %Z"),
        close=float(latest_raw["close"]),
        expected_return=expected_return,
        prob_up=prob_up,
        confidence=confidence,
        volatility=hourly_vol,
        core_drivers=_driver_lines(latest_pred, text_summary),
        historical_matches=(live_snapshot or {}).get("historical_matches", []),
        scenario_note="短周期视角综合了盘中波动外溢与最新新闻情绪。",
        contract_code=_contract_code(live_snapshot),
    )
    payload["trading_window"] = trading_state
    return payload


def predict_tomorrow(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    live_snapshot: dict[str, Any] | None = None,
) -> dict[str, Any]:
    latest_raw = raw.iloc[-1]
    latest_pred = predictions.iloc[-1]
    text_summary = _coerce_summary((live_snapshot or {}).get("text_summary"))
    generated, market_anchor = _forecast_clock(raw, live_snapshot)
    target_day = (generated.tz_localize(None).normalize() + pd.offsets.BDay(1))
    daily_vol = max(float(latest_pred.get("ewma_vol_20", 0.18)) / np.sqrt(252), 0.006)
    expected_return = _safe_float(latest_pred.get("predicted_return", 0.0), 0.0) + 0.18 * text_summary.sentiment_mean + 0.06 * _safe_float(latest_raw.get("event_score", 0.0), 0.0) / 3.0
    prob_up = float(np.clip(_safe_float(latest_pred.get("prob_up_multimodal", latest_pred.get("prob_up", 0.5)), 0.5), 0.01, 0.99))
    confidence = float(np.clip(_safe_float(latest_pred.get("confidence_multimodal", latest_pred.get("confidence", 50.0)), 50.0) + 3, 5, 99))
    return _forecast_payload(
        horizon_key="tomorrow",
        horizon_label="下一个交易日",
        anchor_time=f"market anchor {market_anchor.strftime('%Y-%m-%d')}",
        generated_at=generated.strftime("%Y-%m-%d %H:%M %Z"),
        target_label=f"{target_day.strftime('%Y-%m-%d')} 下一个交易日",
        target_start=target_day.strftime("%Y-%m-%d"),
        target_end=target_day.strftime("%Y-%m-%d"),
        close=float(latest_raw["close"]),
        expected_return=expected_return,
        prob_up=prob_up,
        confidence=confidence,
        volatility=daily_vol,
        core_drivers=_driver_lines(latest_pred, text_summary),
        historical_matches=(live_snapshot or {}).get("historical_matches", []),
        scenario_note="日频预测综合了基准模型、文本偏置与事件分数延续效应。",
        contract_code=_contract_code(live_snapshot),
    )


def predict_one_to_two_weeks(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    live_snapshot: dict[str, Any] | None = None,
    horizon_predictions: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    latest_raw = raw.iloc[-1]
    has_horizon_model = _has_horizon_frame(horizon_predictions, "swing_10d")
    latest_pred = _latest_horizon_row(horizon_predictions, "swing_10d", predictions.iloc[-1])
    text_summary = _coerce_summary((live_snapshot or {}).get("text_summary"))
    generated, market_anchor = _forecast_clock(raw, live_snapshot)
    target_start = generated.tz_localize(None).normalize() + pd.offsets.BDay(1)
    target_end = generated.tz_localize(None).normalize() + pd.offsets.BDay(10)
    swing_vol = max(float(latest_pred.get("ewma_vol_20", 0.18)) * np.sqrt(10 / 252), 0.014)
    apparent_demand = max(abs(_safe_float(latest_raw.get("apparent_demand_tons", 0.0), 0.0)), 1.0)
    supply_gap = _safe_float(latest_raw.get("mine_import_tons", 0.0), 0.0) + _safe_float(latest_raw.get("refined_output_tons", 0.0), 0.0) - _safe_float(latest_raw.get("apparent_demand_tons", 0.0), 0.0)
    supply_bias = float(np.tanh(-supply_gap / apparent_demand) * 0.015)
    basis_bias = float(np.tanh(_safe_float(latest_raw.get("spot_premium", 0.0), 0.0) / max(_safe_float(latest_raw.get("close", 1.0), 1.0), 1.0) * 20.0) * 0.006)
    trend_20 = _trend_return(raw, 20)
    expected_return = _scaled_horizon_return(
        base_return=_safe_float(latest_pred.get("predicted_return", 0.0), 0.0),
        horizon_days=10,
        trend_return=trend_20,
        regime=str(latest_pred.get("regime", "NARROW_RANGE")),
        text_bias=0.040 * text_summary.sentiment_mean,
        extra_bias=supply_bias + basis_bias,
        cap=get_horizon_spec("one_to_two_weeks").max_center_offset,
    )
    base_prob = _safe_float(latest_pred.get("prob_up_multimodal", latest_pred.get("prob_up", 0.5)), 0.5)
    prob_up = _probability_from_expected_return(expected_return, swing_vol, base_prob)
    confidence = float(
        np.clip(
            _safe_float(latest_pred.get("confidence_multimodal", latest_pred.get("confidence", 50.0)), 50.0)
            + 5 * (1 - text_summary.severe_event_probability)
            + (4 if has_horizon_model else -1),
            5,
            99,
        )
    )
    return _forecast_payload(
        horizon_key="one_to_two_weeks",
        horizon_label="未来1-2周",
        anchor_time=f"market anchor {market_anchor.strftime('%Y-%m-%d')}",
        generated_at=generated.strftime("%Y-%m-%d %H:%M %Z"),
        target_label=f"{target_start.strftime('%Y-%m-%d')} to {target_end.strftime('%Y-%m-%d')}",
        target_start=target_start.strftime("%Y-%m-%d"),
        target_end=target_end.strftime("%Y-%m-%d"),
        close=float(latest_raw["close"]),
        expected_return=expected_return,
        prob_up=prob_up,
        confidence=confidence,
        volatility=swing_vol,
        core_drivers=_driver_lines(latest_pred, text_summary),
        historical_matches=(live_snapshot or {}).get("historical_matches", []),
        scenario_note="波段预测重点考虑库存、供需缺口与市场状态延续性。",
        contract_code=_contract_code(live_snapshot),
    )


def predict_one_to_three_months(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    live_snapshot: dict[str, Any] | None = None,
    horizon_predictions: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    latest_raw = raw.iloc[-1]
    has_horizon_model = _has_horizon_frame(horizon_predictions, "trend_60d")
    latest_pred = _latest_horizon_row(horizon_predictions, "trend_60d", predictions.iloc[-1])
    text_summary = _coerce_summary((live_snapshot or {}).get("text_summary"))
    generated, market_anchor = _forecast_clock(raw, live_snapshot)
    target_start = generated.tz_localize(None).normalize() + pd.offsets.BDay(1)
    target_end = target_start + pd.DateOffset(months=3)
    trend_vol = max(float(latest_pred.get("ewma_vol_20", 0.18)) * np.sqrt(40 / 252), 0.025)
    macro_drag = -0.015 * (_safe_float(latest_raw.get("dollar_index", 100.0), 100.0) / 100.0 - 1.0)
    demand_lift = 0.010 * _safe_float(latest_raw.get("pv_demand_yoy", 0.0), 0.0) + 0.008 * _safe_float(latest_raw.get("semi_demand_yoy", 0.0), 0.0)
    trend_60 = _trend_return(raw, 60)
    expected_return = _scaled_horizon_return(
        base_return=_safe_float(latest_pred.get("predicted_return", 0.0), 0.0),
        horizon_days=40,
        trend_return=trend_60,
        regime=str(latest_pred.get("regime", "NARROW_RANGE")),
        text_bias=0.030 * text_summary.sentiment_mean,
        extra_bias=demand_lift + macro_drag,
        cap=get_horizon_spec("one_to_three_months").max_center_offset,
    )
    base_prob = _safe_float(latest_pred.get("prob_up_multimodal", latest_pred.get("prob_up", 0.5)), 0.5)
    prob_up = _probability_from_expected_return(expected_return, trend_vol, base_prob)
    confidence = float(
        np.clip(
            _safe_float(latest_pred.get("confidence_multimodal", latest_pred.get("confidence", 50.0)), 50.0)
            - 4
            + 6 * (1 - text_summary.severe_event_probability)
            + (3 if has_horizon_model else -2),
            5,
            99,
        )
    )
    return _forecast_payload(
        horizon_key="one_to_three_months",
        horizon_label="未来1-3个月",
        anchor_time=f"market anchor {market_anchor.strftime('%Y-%m-%d')}",
        generated_at=generated.strftime("%Y-%m-%d %H:%M %Z"),
        target_label=f"{target_start.strftime('%Y-%m-%d')} to {target_end.strftime('%Y-%m-%d')}",
        target_start=target_start.strftime("%Y-%m-%d"),
        target_end=target_end.strftime("%Y-%m-%d"),
        close=float(latest_raw["close"]),
        expected_return=expected_return,
        prob_up=prob_up,
        confidence=confidence,
        volatility=trend_vol,
        core_drivers=_driver_lines(latest_pred, text_summary),
        historical_matches=(live_snapshot or {}).get("historical_matches", []),
        scenario_note="趋势预测重点考虑中期需求、宏观压力与尾部风险提示。",
        contract_code=_contract_code(live_snapshot),
    )


def build_live_prediction_cards(
    raw: pd.DataFrame,
    predictions: pd.DataFrame,
    live_snapshot: dict[str, Any] | None = None,
    horizon_predictions: dict[str, pd.DataFrame] | None = None,
) -> dict[str, Any]:
    generated_at = pd.Timestamp.now(tz="Asia/Hong_Kong").isoformat()
    cards = {
        "next_5m": predict_next_minutes(raw, predictions, live_snapshot, horizon_key="next_5m"),
        "next_15m": predict_next_minutes(raw, predictions, live_snapshot, horizon_key="next_15m"),
        "next_30m": predict_next_minutes(raw, predictions, live_snapshot, horizon_key="next_30m"),
        "next_hour": predict_next_hour(raw, predictions, live_snapshot),
        "tomorrow": predict_tomorrow(raw, predictions, live_snapshot),
        "one_to_two_weeks": predict_one_to_two_weeks(raw, predictions, live_snapshot, horizon_predictions),
        "one_to_three_months": predict_one_to_three_months(raw, predictions, live_snapshot, horizon_predictions),
    }
    return _json_sanitize({"generated_at": generated_at, "cards": cards})
