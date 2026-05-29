from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping


HORIZON_NEUTRAL_TARGETS = {
    "next_5m": (0.30, 0.58),
    "next_15m": (0.25, 0.55),
    "next_30m": (0.20, 0.52),
    "next_hour": (0.18, 0.50),
    "tomorrow": (0.12, 0.45),
    "one_to_two_weeks": (0.10, 0.40),
    "one_to_three_months": (0.08, 0.35),
}


@dataclass
class DirectionCandidate:
    key: str
    name: str
    direction: str
    score: float
    confidence: float
    weight: float
    evidence: str
    recent_hit_rate: float | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _direction(score: float, threshold: float = 0.04) -> str:
    if score > threshold:
        return "bullish"
    if score < -threshold:
        return "bearish"
    return "neutral"


def _extract_driver_score(card: Mapping[str, Any], keys: tuple[str, ...]) -> float:
    total = 0.0
    count = 0
    for raw in card.get("core_drivers", []) or []:
        text = str(raw)
        for key in keys:
            if key in text:
                if ":" in text:
                    total += _safe_float(text.split(":", 1)[1], 0.0)
                    count += 1
                elif "+" in text or "利多" in text:
                    total += 1.0
                    count += 1
                elif "-" in text or "利空" in text:
                    total -= 1.0
                    count += 1
    if count == 0:
        return 0.0
    return math.tanh(total / max(count, 1) / 1000.0)


def _event_score(news_summary: Mapping[str, Any]) -> float:
    sentiment = _safe_float(news_summary.get("weighted_sentiment"), 0.0)
    weight = _safe_float(news_summary.get("confidence_weight"), 0.0)
    direction = str(news_summary.get("event_factor_direction") or "")
    base = sentiment * max(weight, 0.15 if direction in {"bullish", "bearish"} else 0.0)
    if direction == "bullish":
        base += min(weight, 1.0) * 0.20
    elif direction == "bearish":
        base -= min(weight, 1.0) * 0.20
    return _clip(base, -1.0, 1.0)


def _validation_hit_rate(profile: Mapping[str, Any]) -> tuple[float | None, int]:
    for key in ("direction_hit_rate", "directional_accuracy", "hit_rate"):
        if key in profile:
            return _safe_float(profile.get(key), 0.0), int(_safe_float(profile.get("effective_sample_count"), 0))
    for value in profile.values():
        if isinstance(value, Mapping):
            for key in ("direction_hit_rate", "directional_accuracy", "hit_rate"):
                if key in value:
                    return _safe_float(value.get(key), 0.0), int(_safe_float(value.get("effective_sample_count"), 0))
    return None, 0


def _candidate(key: str, name: str, score: float, confidence: float, weight: float, evidence: str, hit: float | None) -> DirectionCandidate:
    return DirectionCandidate(
        key=key,
        name=name,
        direction=_direction(score),
        score=round(float(score), 6),
        confidence=round(float(_clip(confidence, 0.0, 1.0)), 6),
        weight=round(float(_clip(weight, 0.0, 1.0)), 6),
        evidence=evidence,
        recent_hit_rate=hit,
    )


def build_direction_ensemble(
    card: Mapping[str, Any],
    *,
    news_policy: Mapping[str, Any] | None = None,
    validation_profile: Mapping[str, Any] | None = None,
    data_quality_score: float = 0.65,
    minute_data_available: bool = False,
) -> dict[str, Any]:
    horizon = str(card.get("horizon_key") or card.get("horizon") or "")
    anchor = _safe_float(card.get("anchor_price") or card.get("anchor_close") or card.get("asof_price"), 0.0)
    center = _safe_float(card.get("price_center"), anchor)
    expected_return = _safe_float(card.get("expected_return"), center / anchor - 1.0 if anchor > 0 else 0.0)
    raw_prob_up = _clip(_safe_float(card.get("prob_up"), 0.5), 0.0, 1.0)
    hit_rate, sample_count = _validation_hit_rate(validation_profile or {})
    news_summary = {}
    if isinstance(news_policy, Mapping):
        news_summary = news_policy.get("summary", {}) if isinstance(news_policy.get("summary"), Mapping) else news_policy

    minute_reference_only = horizon in {"next_5m", "next_15m", "next_30m", "next_hour", "h5m", "h15m", "h30m", "h1h"} and not minute_data_available
    price_score = _clip(expected_return * 18.0, -1.0, 1.0)
    momentum_score = _clip((raw_prob_up - 0.5) * 2.0 + price_score * 0.30 + _extract_driver_score(card, ("return", "momentum", "obv")), -1.0, 1.0)
    mean_reversion_score = _clip(-_extract_driver_score(card, ("rsi", "boll", "basis_mom")), -1.0, 1.0)
    volume_oi_score = _clip(_extract_driver_score(card, ("volume", "open_interest", "持仓", "成交")), -1.0, 1.0)
    basis_inventory_score = _clip(_extract_driver_score(card, ("basis", "warehouse", "inventory", "库存", "仓单")), -1.0, 1.0)
    lme_score = _clip(_extract_driver_score(card, ("lme", "伦锡", "美元", "汇率")), -1.0, 1.0)
    news_score = _event_score(news_summary)
    ml_score = _clip((raw_prob_up - 0.5) * 1.35 + price_score * 0.20, -1.0, 1.0)

    candidates = [
        _candidate("momentum", "短周期动量", momentum_score, 0.60, 0.18, "价格动量与 OBV/收益因子", hit_rate),
        _candidate("mean_reversion", "均值回归", mean_reversion_score, 0.48, 0.10, "RSI/布林/基差偏离", hit_rate),
        _candidate("volume_oi", "成交量/持仓", volume_oi_score, 0.52, 0.12, "量仓变化确认", hit_rate),
        _candidate("basis_inventory", "基差/库存/仓单", basis_inventory_score, 0.56, 0.14, "产业链与库存压力", hit_rate),
        _candidate("lme_linkage", "伦锡/宏观联动", lme_score, 0.45, 0.09, "外盘、美元与汇率参考", hit_rate),
        _candidate("news_policy", "新闻政策事件", news_score, 0.62 if news_score else 0.30, 0.17, "新闻政策事件方向偏置", hit_rate),
        _candidate("ml_classifier", "轻量 ML 分类器", ml_score, 0.58, 0.20, "结构化因子方向分类", hit_rate),
    ]

    weighted = sum(c.score * c.confidence * c.weight for c in candidates)
    total_weight = sum(c.confidence * c.weight for c in candidates) or 1.0
    ensemble_score = _clip(weighted / total_weight, -1.0, 1.0)
    bullish = sum(1 for c in candidates if c.direction == "bullish")
    bearish = sum(1 for c in candidates if c.direction == "bearish")
    non_neutral = max(1, bullish + bearish)
    consensus = max(bullish, bearish) / non_neutral
    conflict_count = min(bullish, bearish)

    ensemble_prob_up = _clip(0.5 + math.tanh(ensemble_score * 1.2) * 0.32, 0.18, 0.82)
    blended_prob_up = _clip(raw_prob_up * 0.35 + ensemble_prob_up * 0.65, 0.18, 0.82)
    confidence = _clip(38 + abs(ensemble_score) * 46 + (consensus - 0.5) * 18, 16, 92)
    diagnosis: list[str] = []
    hard_downgrade: list[str] = []
    if data_quality_score < 0.35:
        hard_downgrade.append("data_quality_too_low")
        diagnosis.append("data_quality_too_low")
    elif data_quality_score < 0.50:
        diagnosis.append("data_quality_warning")
        confidence *= 0.88
    if hit_rate is not None and sample_count >= 15 and hit_rate < 0.43:
        hard_downgrade.append("recent_direction_hit_weak")
        diagnosis.append("recent_direction_hit_weak")
    elif hit_rate is None:
        diagnosis.append("insufficient_validation_samples")
    if conflict_count >= 3:
        hard_downgrade.append("candidate_conflict_high")
        diagnosis.append("candidate_conflict_high")
    elif conflict_count > 0:
        diagnosis.append("candidate_conflict_present")
    if abs(blended_prob_up - 0.5) < 0.035 and abs(ensemble_score) < 0.12:
        hard_downgrade.append("probability_edge_insufficient")
        diagnosis.append("probability_edge_insufficient")
    if minute_reference_only:
        diagnosis.append("minute_data_insufficient_reference_only")
        confidence *= 0.90
        if data_quality_score < 0.50:
            hard_downgrade.append("short_horizon_reference_low_quality")

    probability_edge = max(abs(blended_prob_up - 0.5) - 0.015, 0.0) * 2.6
    score_edge = abs(ensemble_score) * 0.82
    consensus_edge = max(consensus - 0.50, 0.0) * 0.72
    quality_penalty = 0.18 if data_quality_score < 0.35 else (0.08 if data_quality_score < 0.50 else 0.0)
    conflict_penalty = min(conflict_count, 3) * 0.045
    minute_penalty = 0.06 if minute_reference_only else 0.0
    p_edge = _clip(probability_edge + score_edge + consensus_edge - quality_penalty - conflict_penalty - minute_penalty, 0.04, 0.88)
    edge_score = _clip(p_edge * (1.0 if ensemble_score >= 0 else -1.0), -1.0, 1.0)

    neutral_lo, neutral_hi = HORIZON_NEUTRAL_TARGETS.get(horizon, (0.18, 0.52))
    direction = "neutral"
    min_edge = max(0.22, 1.0 - neutral_hi)
    if not hard_downgrade and p_edge >= min_edge and blended_prob_up >= 0.555 and ensemble_score > 0:
        direction = "bullish"
    elif not hard_downgrade and p_edge >= min_edge and blended_prob_up <= 0.445 and ensemble_score < 0:
        direction = "bearish"

    if direction == "neutral":
        p_neutral = _clip(1.0 - p_edge + min(len(hard_downgrade), 3) * 0.06, neutral_lo, min(0.88, neutral_hi + 0.22))
        blended_prob_up = _clip(0.5 + (blended_prob_up - 0.5) * 0.55, 0.40, 0.60)
        confidence = min(confidence, 62.0)
    else:
        p_neutral = _clip(1.0 - p_edge, 0.04, min(0.36, neutral_hi))

    directional_mass = max(0.0, 1.0 - p_neutral)
    p_up_3way = directional_mass * blended_prob_up
    p_down_3way = directional_mass * (1.0 - blended_prob_up)
    total_3way = p_up_3way + p_down_3way + p_neutral
    p_up_3way, p_down_3way, p_neutral = p_up_3way / total_3way, p_down_3way / total_3way, p_neutral / total_3way

    signal_strength = "neutral"
    if direction == "bullish":
        signal_strength = "strong_up" if confidence >= 72 and p_edge >= 0.46 else "weak_up"
    elif direction == "bearish":
        signal_strength = "strong_down" if confidence >= 72 and p_edge >= 0.46 else "weak_down"
    direction_label = {"bullish": "偏多", "bearish": "偏空", "neutral": "中性/方向优势不足"}[direction]
    ranked = sorted(candidates, key=lambda c: abs(c.score) * c.confidence * c.weight, reverse=True)
    return {
        "direction": direction,
        "direction_label": direction_label,
        "score": round(ensemble_score, 4),
        "raw_prob_up": round(raw_prob_up, 4),
        "adjusted_prob_up": round(blended_prob_up, 4),
        "prob_up": round(blended_prob_up, 4),
        "prob_down": round(1.0 - blended_prob_up, 4),
        "p_up": round(p_up_3way, 4),
        "p_down": round(p_down_3way, 4),
        "p_neutral": round(p_neutral, 4),
        "p_edge": round(p_edge, 4),
        "edge_score": round(edge_score, 4),
        "confidence": round(confidence, 2),
        "consensus": round(consensus, 4),
        "conflict_count": conflict_count,
        "strong_direction": direction != "neutral",
        "downgrade_reasons": hard_downgrade,
        "neutral_rate_diagnosis": diagnosis or (["edge_detected"] if direction != "neutral" else ["probability_edge_insufficient"]),
        "signal_strength": signal_strength,
        "sample_reference": "真实/回测兑现样本" if hit_rate is not None else "样本不足，候选弱权重",
        "event_summary": news_summary,
        "candidates": [c.to_dict() for c in ranked],
        "candidate_weights": {c.key: round(c.weight, 4) for c in candidates},
    }


def apply_direction_ensemble_to_payload(
    payload: Mapping[str, Any],
    *,
    news_policy: Mapping[str, Any] | None = None,
    validation_profile: Mapping[str, Any] | None = None,
    data_quality_score: float = 0.65,
    minute_data_available: bool = False,
) -> dict[str, Any]:
    out = dict(payload or {})
    cards = out.get("cards", {})
    if not isinstance(cards, dict):
        return out
    for key, card in cards.items():
        if not isinstance(card, dict):
            continue
        card.setdefault("horizon", str(key))
        card.setdefault("horizon_key", str(key))
        card_news = card.get("news_policy_payload") if isinstance(card.get("news_policy_payload"), Mapping) else news_policy
        ensemble = build_direction_ensemble(
            card,
            news_policy=card_news or news_policy or {},
            validation_profile=validation_profile or {},
            data_quality_score=float(card.get("data_quality_score", data_quality_score) or data_quality_score),
            minute_data_available=bool(card.get("minute_data_available", minute_data_available) or minute_data_available),
        )
        card["direction_ensemble"] = ensemble
        card["direction_candidate_scores"] = ensemble["candidates"]
        card["candidate_weights"] = ensemble["candidate_weights"]
        card["raw_prob_up"] = ensemble["raw_prob_up"]
        card["prob_up"] = ensemble["prob_up"]
        card["prob_down"] = ensemble["prob_down"]
        card["p_up"] = ensemble["p_up"]
        card["p_down"] = ensemble["p_down"]
        card["p_neutral"] = ensemble["p_neutral"]
        card["prob_neutral"] = ensemble["p_neutral"]
        card["p_edge"] = ensemble["p_edge"]
        card["edge_score"] = ensemble["edge_score"]
        card["direction_key"] = ensemble["direction"]
        card["direction_label"] = ensemble["direction_label"]
        card["confidence_score"] = min(float(card.get("confidence_score", 1.0) or 1.0), ensemble["confidence"] / 100.0)
        card["signal_strength"] = ensemble["signal_strength"]
        card["neutral_rate_diagnosis"] = ensemble["neutral_rate_diagnosis"]
        card["direction_gate"] = {
            "status": "通过" if ensemble["direction"] != "neutral" else "方向优势不足/参考",
            "reasons": ensemble["downgrade_reasons"] or ensemble["neutral_rate_diagnosis"],
        }
        card["news_policy_impact"] = ensemble["event_summary"]
    return out
