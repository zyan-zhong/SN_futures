from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

from .config import ProjectPaths
from .event_schema import EVENT_FEATURE_NAMES, max_window_hours, source_tier_weight, window_hours_for_horizon
from .event_store import ingest_articles, load_events, load_provider_status, mark_event_usage, update_provider_status
from .event_taxonomy import parse_time
from .news_store import load_recent_articles


def _snapshot_path(output_dir: Path | None = None) -> Path:
    out = output_dir or ProjectPaths().output_dir
    return out / "sn_live_snapshot.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def sync_event_store_from_news(output_dir: Path | None = None) -> dict[str, Any]:
    snapshot = _read_json(_snapshot_path(output_dir))
    articles: list[dict[str, Any]] = []
    if isinstance(snapshot.get("articles"), list):
        articles.extend([row for row in snapshot["articles"] if isinstance(row, dict)])
    articles.extend(load_recent_articles(limit=400))
    seen: set[tuple[str, str, str]] = set()
    unique: list[dict[str, Any]] = []
    for article in articles:
        key = (
            str(article.get("event_id") or ""),
            str(article.get("title") or ""),
            str(article.get("url") or article.get("canonical_url") or article.get("source_url") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        unique.append(article)
    inserted = ingest_articles(unique, batch_id=str(snapshot.get("generated_at", "")))
    statuses = snapshot.get("source_status", []) if isinstance(snapshot.get("source_status"), list) else []
    update_provider_status([row for row in statuses if isinstance(row, dict)])
    return {
        "snapshot_articles": len(snapshot.get("articles", [])) if isinstance(snapshot.get("articles"), list) else 0,
        "unique_articles": len(unique),
        "inserted_or_updated": inserted,
        "source_status_count": len(statuses),
    }


def _age_hours(event: dict[str, Any], prediction_time: pd.Timestamp) -> float | None:
    ts = parse_time(event.get("available_at"))
    if ts is None:
        return None
    return max(0.0, (prediction_time - ts).total_seconds() / 3600.0)


def _apply_prediction_time_decay(events: list[dict[str, Any]], prediction_time: pd.Timestamp) -> list[dict[str, Any]]:
    adjusted: list[dict[str, Any]] = []
    for event in events:
        row = dict(event)
        age = _age_hours(row, prediction_time)
        if age is None:
            adjusted.append(row)
            continue
        decay = float(max(0.06, min(1.0, math.exp(-age / 168.0))))
        source_conf = float(row.get("source_confidence") or source_tier_weight(str(row.get("source_tier") or "")))
        impact = float(row.get("impact_score") or 0.0)
        direction_confidence = max(float(row.get("direction_confidence") or 0.0), 0.18)
        row["time_decay_weight"] = round(decay, 5)
        row["final_event_weight"] = round(max(0.0, min(1.0, source_conf * impact * direction_confidence * decay)), 5)
        adjusted.append(row)
    return adjusted


def _reject_reason(event: dict[str, Any], horizon: str, prediction_time: pd.Timestamp) -> str:
    source_published = parse_time(event.get("source_published_at") or event.get("published_at"))
    if source_published is None:
        return "missing_source_published_at"
    if source_published > prediction_time:
        return "source_published_at_after_prediction_time"
    if float(event.get("event_time_confidence") or 0.0) < 0.5:
        return "low_event_time_confidence"
    available = parse_time(event.get("available_at"))
    if available is None:
        return "no_available_at"
    if available > prediction_time:
        return "prediction_time_alignment_failed"
    if not event.get("canonical_url") and not event.get("raw_url"):
        return "no_url"
    if not event.get("symbol_tags") and float(event.get("relevance_score") or 0.0) < 0.18:
        return "no_symbol_match"
    age = _age_hours(event, prediction_time)
    if age is None:
        return "no_available_at"
    if age > max_window_hours(horizon):
        return "event_window_mismatch"
    if float(event.get("direction_confidence") or 0.0) < 0.12:
        return "low_confidence"
    min_weight = 0.020 if event.get("source_tier") == "tier1" else 0.035
    if float(event.get("final_event_weight") or 0.0) < min_weight:
        return "low_impact"
    return ""


def _event_public_view(event: dict[str, Any], *, used: bool, reason: str = "") -> dict[str, Any]:
    impact = float(event.get("impact_score") or 0.0)
    return {
        "event_id": event.get("event_id", ""),
        "title": event.get("title", ""),
        "summary": event.get("summary", ""),
        "source": event.get("source", ""),
        "provider": event.get("provider", ""),
        "source_tier": event.get("source_tier", ""),
        "raw_url": event.get("raw_url", ""),
        "canonical_url": event.get("canonical_url", ""),
        "url_sanitized": event.get("url_sanitized") or event.get("canonical_url") or event.get("raw_url", ""),
        "final_open_url": event.get("final_open_url") or event.get("canonical_url") or event.get("raw_url", ""),
        "url": event.get("canonical_url") or event.get("raw_url", ""),
        "source_url": event.get("canonical_url") or event.get("raw_url", ""),
        "url_status": event.get("url_status", ""),
        "blocked_reason": event.get("blocked_reason", ""),
        "event_group_id": event.get("event_group_id", ""),
        "published_at": event.get("published_at", ""),
        "source_published_at": event.get("source_published_at") or event.get("published_at", ""),
        "fetched_at": event.get("fetched_at", ""),
        "available_at": event.get("available_at", ""),
        "event_time_confidence": float(event.get("event_time_confidence") or 0.0),
        "region": event.get("region", ""),
        "category": event.get("category", ""),
        "language": event.get("language", ""),
        "event_type": event.get("event_type", ""),
        "direction_bias": event.get("direction_bias", "neutral"),
        "direction_contribution": event.get("direction_bias", "neutral"),
        "direction_confidence": float(event.get("direction_confidence") or 0.0),
        "impact_score": impact,
        "sentiment_score": float(event.get("sentiment_score") or 0.0),
        "time_decay_weight": float(event.get("time_decay_weight") or 0.0),
        "event_decay_weight": float(event.get("time_decay_weight") or 0.0),
        "confidence_weight": float(event.get("final_event_weight") or 0.0),
        "model_weight": float(event.get("final_event_weight") or 0.0),
        "relevance_score": float(event.get("relevance_score") or 0.0),
        "source_reliability_score": float(event.get("source_reliability_score") or event.get("source_confidence") or 0.0),
        "used_in_model": used,
        "included_in_model": used,
        "enters_model": used,
        "rejected_reason": reason,
        "rejection_reason": reason,
        "content_hash": event.get("content_hash", ""),
        "impact_level": "高" if impact >= 0.55 else ("中" if impact >= 0.30 else "低"),
        "entity_tags": event.get("entity_tags", []),
        "symbol_tags": event.get("symbol_tags", []),
    }


def _feature_bucket(rows: list[dict[str, Any]]) -> dict[str, float]:
    bucket = {name: 0.0 for name in EVENT_FEATURE_NAMES}
    bucket["event_count"] = float(len(rows))
    bucket["high_impact_event_count"] = float(sum(1 for row in rows if float(row.get("impact_score") or 0.0) >= 0.55))
    bucket["authoritative_event_count"] = float(sum(1 for row in rows if row.get("source_tier") == "tier1"))
    if rows:
        total_weight = sum(float(row.get("final_event_weight") or 0.0) for row in rows) or 1.0
        bucket["news_sentiment"] = float(
            sum(float(row.get("sentiment_score") or 0.0) * float(row.get("final_event_weight") or 0.0) for row in rows) / total_weight
        )
    for row in rows:
        weight = float(row.get("final_event_weight") or 0.0)
        impact = float(row.get("impact_score") or 0.0)
        bias = str(row.get("direction_bias") or "neutral")
        event_type = str(row.get("event_type") or "")
        if bias == "bullish":
            bucket["bullish_event_score"] += weight
            bucket["demand_positive_score"] += float(row.get("demand_score") or impact) * weight
        elif bias == "bearish":
            bucket["bearish_event_score"] += weight
        elif bias in {"volatility", "mixed"}:
            bucket["volatility_event_score"] += weight
        if event_type in {"exchange_notice", "margin_change", "fee_change", "limit_change"}:
            bucket["exchange_notice_flag"] = 1.0
            bucket["policy_event_count"] += 1.0
        if event_type in {"supply_disruption", "smelter_output_change", "import_export", "geopolitical_supply"}:
            bucket["supply_disruption_score"] += float(row.get("supply_score") or impact) * weight
        if event_type == "inventory_change":
            bucket["inventory_event_score"] += float(row.get("inventory_score") or impact) * weight
        if event_type == "warehouse_receipt_change":
            bucket["warehouse_receipt_event_score"] += float(row.get("inventory_score") or impact) * weight
        if event_type in {"macro_policy", "currency_move"}:
            bucket["macro_policy_score"] += float(row.get("macro_score") or impact) * weight
        if event_type == "option_iv_change":
            bucket["option_iv_event_score"] += float(row.get("volatility_score") or impact) * weight
        bucket["event_shock_score"] += max(float(row.get("volatility_score") or 0.0), weight if impact >= 0.55 else 0.0)
    return {key: round(float(value), 6) for key, value in bucket.items()}


def build_event_evidence(
    horizon: str = "tomorrow",
    *,
    prediction_time: str | pd.Timestamp | None = None,
    output_dir: Path | None = None,
    limit: int = 500,
) -> dict[str, Any]:
    sync_stats = sync_event_store_from_news(output_dir)
    prediction_ts = pd.Timestamp(prediction_time) if prediction_time is not None else pd.Timestamp.now(tz="Asia/Hong_Kong")
    if prediction_ts.tzinfo is None:
        prediction_ts = prediction_ts.tz_localize("Asia/Hong_Kong")
    else:
        prediction_ts = prediction_ts.tz_convert("Asia/Hong_Kong")

    events = _apply_prediction_time_decay(load_events(limit=limit), prediction_ts)
    recognized = [event for event in events if event.get("symbol_tags") or float(event.get("relevance_score") or 0.0) >= 0.18]
    used: list[dict[str, Any]] = []
    rejected: dict[str, str] = {}
    rejected_breakdown: Counter[str] = Counter()
    for event in recognized:
        reason = _reject_reason(event, horizon, prediction_ts)
        if reason:
            rejected[str(event.get("event_id", ""))] = reason
            rejected_breakdown[reason] += 1
            continue
        used.append(event)
    mark_event_usage({str(event.get("event_id")) for event in used}, horizon=horizon, rejected=rejected)

    window_features: dict[str, dict[str, float]] = {}
    features = {name: 0.0 for name in EVENT_FEATURE_NAMES}
    for label, hours in window_hours_for_horizon(horizon):
        rows = [event for event in used if (_age_hours(event, prediction_ts) or 999999.0) <= hours]
        bucket = _feature_bucket(rows)
        window_features[label] = bucket
        features = bucket

    bullish_score = sum(float(row.get("final_event_weight") or 0.0) for row in used if row.get("direction_bias") == "bullish")
    bearish_score = sum(float(row.get("final_event_weight") or 0.0) for row in used if row.get("direction_bias") == "bearish")
    vol_score = sum(float(row.get("final_event_weight") or 0.0) for row in used if row.get("direction_bias") in {"volatility", "mixed"})
    total_direction = bullish_score + bearish_score + vol_score
    weighted_sentiment = 0.0 if total_direction <= 0 else (bullish_score - bearish_score) / max(total_direction, 1e-9)
    if not used:
        factor_direction = "unavailable" if recognized else "neutral"
        contribution_label = "识别到事件但未满足 available_at、相关性、窗口或权重要求" if recognized else "暂无沪锡相关可用事件"
    elif abs(weighted_sentiment) < 0.10 and vol_score > max(bullish_score, bearish_score):
        factor_direction = "volatility"
        contribution_label = "新闻政策主要提示波动风险"
    elif weighted_sentiment > 0.10:
        factor_direction = "bullish"
        contribution_label = "新闻政策因子偏多"
    elif weighted_sentiment < -0.10:
        factor_direction = "bearish"
        contribution_label = "新闻政策因子偏空"
    else:
        factor_direction = "neutral"
        contribution_label = "新闻政策因子中性"

    event_feature_hash = hashlib.sha256(
        json.dumps(
            {"horizon": horizon, "used": [row.get("event_id") for row in used], "features": features, "windows": window_features},
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:16]
    feature_nonzero = sum(1 for val in features.values() if abs(float(val or 0.0)) > 1e-12)
    used_public = [_event_public_view(row, used=True) for row in used]
    rejected_public = [_event_public_view(row, used=False, reason=rejected.get(str(row.get("event_id", "")), "")) for row in recognized if str(row.get("event_id", "")) in rejected]
    events_public = used_public + rejected_public
    provider_rows = load_provider_status()
    confidence_weight = min(1.0, total_direction)
    summary = {
        "weighted_sentiment": round(float(weighted_sentiment), 6),
        "confidence_weight": round(float(confidence_weight), 6),
        "direction_contribution": contribution_label,
        "contribution_label": contribution_label,
        "event_factor_direction": factor_direction,
        "event_feature_hash": event_feature_hash,
        "included_count": len(used),
        "recognized_count": len(recognized),
        "rejected_count": len(rejected_public),
        "failure_reason": "" if used else contribution_label,
    }
    return {
        "horizon": horizon,
        "prediction_time": prediction_ts.isoformat(),
        "sync_stats": sync_stats,
        "recognized_event_count": len(recognized),
        "valid_event_count": len(used),
        "used_in_model_event_count": len(used),
        "rejected_event_count": len(rejected_public),
        "rejected_reason_breakdown": dict(rejected_breakdown),
        "event_source_count": len(set(str(event.get("provider") or event.get("source") or "") for event in events)),
        "tier_counts": dict(Counter(str(event.get("source_tier") or "tier3") for event in events)),
        "event_feature_nonzero_count": feature_nonzero,
        "event_feature_names_used": [key for key, val in features.items() if abs(float(val or 0.0)) > 1e-12],
        "event_feature_hash": event_feature_hash,
        "features": features,
        "window_features": window_features,
        "summary": summary,
        "events": events_public,
        "recognized_events": events_public,
        "used_events": used_public,
        "rejected_events": rejected_public,
        "top_bullish_events": [row for row in used_public if row.get("direction_bias") == "bullish"][:8],
        "top_bearish_events": [row for row in used_public if row.get("direction_bias") == "bearish"][:8],
        "top_volatility_events": [row for row in used_public if row.get("direction_bias") in {"volatility", "mixed"}][:8],
        "top_risk_events": sorted(used_public, key=lambda row: float(row.get("impact_score") or 0.0), reverse=True)[:8],
        "provider_status": provider_rows,
        "disclaimer": "新闻政策事件仅用于量化投研解释和特征输入，不构成投资建议。",
    }
