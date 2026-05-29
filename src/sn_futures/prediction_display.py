from __future__ import annotations

from typing import Any, Mapping, MutableMapping

import math


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if math.isfinite(out) else default


def _clip(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _direction_key(prob_up: float, p_neutral: float = 0.0) -> str:
    if p_neutral >= 0.45:
        return "neutral"
    if prob_up >= 0.58:
        return "bullish"
    if prob_up <= 0.42:
        return "bearish"
    return "neutral"


def _direction_label(prob_up: float, p_neutral: float = 0.0) -> str:
    key = _direction_key(prob_up, p_neutral)
    if key == "bullish":
        return "偏多"
    if key == "bearish":
        return "偏空"
    return "中性/方向优势不足"


DRIVER_LABELS = {
    "obv_slope_10": ("OBV 量价趋势", "成交量推动的价格趋势强弱"),
    "basis_mom_5": ("基差动量", "期现价差的短期变化方向"),
    "spot_premium_mom": ("现货升贴水动量", "现货相对期货的强弱变化"),
    "return_5": ("5期动量", "最近价格动量"),
    "return_10": ("10期动量", "中短周期价格动量"),
    "rsi": ("RSI 强弱", "价格超买超卖状态"),
    "atr": ("ATR 波动", "近期真实波动范围"),
    "volume_zscore": ("成交量异常", "成交量相对历史水平的偏离"),
    "open_interest_change": ("持仓变化", "持仓量增减对趋势延续的提示"),
    "news_sentiment": ("新闻情绪", "锡相关新闻与政策的方向偏置"),
    "policy_event": ("政策事件", "产业政策、监管或交易所公告影响"),
}


def explain_driver(raw: Any) -> dict[str, Any]:
    """Convert a raw model driver into a Chinese, user-facing explanation.

    The old UI exposed technical keys such as ``obv_slope_10:+5865`` directly.
    This helper keeps the original value for auditability but shows a compact
    research explanation first.
    """

    if isinstance(raw, Mapping):
        name = str(raw.get("name") or raw.get("feature") or raw.get("key") or "")
        value = _safe_float(raw.get("value") or raw.get("contribution") or raw.get("score"), 0.0)
        raw_text = str(raw.get("raw") or raw)
    else:
        raw_text = str(raw)
        if ":" in raw_text:
            name, value_text = raw_text.split(":", 1)
            value = _safe_float(value_text, 0.0)
        else:
            name, value = raw_text, 0.0
    clean = name.strip()
    label, description = DRIVER_LABELS.get(clean, (clean or "模型因子", "模型识别到的价格驱动因子"))
    direction = "利多" if value > 0 else ("利空" if value < 0 else "中性")
    abs_value = abs(value)
    if abs_value >= 1000:
        strength = "高"
    elif abs_value >= 100:
        strength = "中"
    elif abs_value > 0:
        strength = "低"
    else:
        strength = "无明显贡献"
    return {
        "name": label,
        "raw_key": clean,
        "raw_value": value,
        "direction": direction,
        "strength": strength,
        "description": description,
        "raw": raw_text,
        "display": f"{label} · {direction} · 强度{strength}",
    }


def build_data_trust_badges(
    *,
    quality_score: float,
    source_mode: str = "",
    minute_data_available: bool = False,
    fallback_reason: str = "",
) -> list[dict[str, str]]:
    q = _clip(_safe_float(quality_score, 0.0), 0.0, 1.0)
    if q >= 0.75:
        level = "高"
        tone = "good"
    elif q >= 0.50:
        level = "中"
        tone = "warn"
    else:
        level = "低"
        tone = "bad"
    badges = [
        {
            "label": f"数据可信度：{level}",
            "tone": tone,
            "detail": f"综合行情、缓存、源状态后的质量分：{q:.1%}",
        }
    ]
    if minute_data_available:
        badges.append({"label": "短周期快照可用", "tone": "good", "detail": "可用于短线参考与后续验证"})
    else:
        badges.append({"label": "分钟线/快照不足", "tone": "warn", "detail": "短周期仅作为参考，不计入真实命中率"})
    if source_mode:
        badges.append({"label": f"来源：{source_mode}", "tone": "info", "detail": "当前行情/缓存来源模式"})
    if fallback_reason:
        badges.append({"label": "存在回退", "tone": "warn", "detail": fallback_reason})
    return badges


def _normalize_probability_fields(card: MutableMapping[str, Any]) -> None:
    p_up = _safe_float(card.get("p_up"), float("nan"))
    p_down = _safe_float(card.get("p_down"), float("nan"))
    p_neutral = _safe_float(card.get("p_neutral"), float("nan"))
    if not all(math.isfinite(v) for v in (p_up, p_down, p_neutral)):
        prob_up = _clip(_safe_float(card.get("prob_up"), 0.5), 0.0, 1.0)
        prob_neutral = _clip(_safe_float(card.get("prob_neutral"), 0.0), 0.0, 0.85)
        directional_mass = max(0.0, 1.0 - prob_neutral)
        p_up = directional_mass * prob_up
        p_down = directional_mass * (1.0 - prob_up)
        p_neutral = prob_neutral
    total = p_up + p_down + p_neutral
    if total <= 0:
        p_up, p_down, p_neutral = 0.33, 0.33, 0.34
    else:
        p_up, p_down, p_neutral = p_up / total, p_down / total, p_neutral / total
    prob_up = p_up / max(p_up + p_down, 1e-9)
    card["p_up"] = round(float(p_up), 6)
    card["p_down"] = round(float(p_down), 6)
    card["p_neutral"] = round(float(p_neutral), 6)
    card["prob_up"] = round(float(prob_up), 6)
    card["prob_down"] = round(float(1.0 - prob_up), 6)
    card["prob_neutral"] = round(float(p_neutral), 6)
    card["gate_adjusted_prob_up"] = card["prob_up"]


def _profile_hit_rate(profile: Mapping[str, Any], horizon: str) -> float | None:
    for key in (horizon, "overall", "walk_forward_baseline"):
        item = profile.get(key) if isinstance(profile, Mapping) else None
        if isinstance(item, Mapping):
            for metric in ("direction_hit_rate", "directional_accuracy", "hit_rate"):
                if metric in item:
                    return _safe_float(item.get(metric), 0.0)
    for metric in ("direction_hit_rate", "directional_accuracy", "hit_rate"):
        if metric in profile:
            return _safe_float(profile.get(metric), 0.0)
    return None


def _soften_direction(card: MutableMapping[str, Any], severity: float, neutral_add: float = 0.0) -> None:
    """Reduce overconfident directional mass without replacing it by fake 50/50."""

    _normalize_probability_fields(card)
    p_up = _safe_float(card.get("p_up"), 0.33)
    p_down = _safe_float(card.get("p_down"), 0.33)
    p_neutral = _safe_float(card.get("p_neutral"), 0.34)
    severity = _clip(severity, 0.0, 1.0)
    directional_total = p_up + p_down
    if directional_total > 0:
        directional_ratio = p_up / directional_total
    else:
        directional_ratio = 0.5
    softened_ratio = 0.5 + (directional_ratio - 0.5) * (1.0 - severity)
    p_neutral = _clip(p_neutral + neutral_add, 0.0, 0.88)
    directional_mass = 1.0 - p_neutral
    card["p_up"] = directional_mass * softened_ratio
    card["p_down"] = directional_mass * (1.0 - softened_ratio)
    card["p_neutral"] = p_neutral
    _normalize_probability_fields(card)


def _compress_center(card: MutableMapping[str, Any], anchor: float, ratio: float, reason: str) -> None:
    if anchor <= 0:
        return
    center = _safe_float(card.get("price_center"), anchor)
    ratio = _clip(ratio, 0.0, 1.0)
    new_center = anchor + (center - anchor) * ratio
    low = _safe_float(card.get("range_low"), new_center)
    high = _safe_float(card.get("range_high"), new_center)
    half = max(abs(high - low) / 2.0, anchor * 0.002)
    card["price_center"] = new_center
    card["range_low"] = max(0.0, new_center - half)
    card["range_high"] = new_center + half
    card["expected_return"] = new_center / anchor - 1.0
    card["center_offset_pct"] = card["expected_return"]
    card.setdefault("price_guard_reasons", []).append(reason)


def apply_direction_gate(
    payload: Mapping[str, Any],
    validation_profile: Mapping[str, Any] | None = None,
    *,
    data_quality_score: float = 0.65,
    source_mode: str = "",
    minute_data_available: bool = False,
) -> dict[str, Any]:
    """Apply final display-time consistency checks without faking probabilities.

    This gate intentionally avoids the old "set everything to 50%" behavior.
    It marks uncertainty, lowers confidence, and compresses unrealistic price
    drift only when the evidence is insufficient or contradictory.
    """

    out = dict(payload or {})
    cards = out.get("cards", {})
    if not isinstance(cards, dict):
        return out
    profile = validation_profile or {}
    global_quality = _clip(_safe_float(data_quality_score, 0.65), 0.0, 1.0)
    for horizon, raw_card in cards.items():
        if not isinstance(raw_card, MutableMapping):
            continue
        card = raw_card
        horizon_key = str(card.get("horizon_key") or card.get("horizon") or horizon)
        card["horizon_key"] = horizon_key
        card.setdefault("raw_prob_up", _safe_float(card.get("prob_up"), 0.5))
        _normalize_probability_fields(card)
        quality = _clip(_safe_float(card.get("data_quality_score"), global_quality), 0.0, 1.0)
        anchor = _safe_float(card.get("anchor_price") or card.get("anchor_close") or card.get("asof_price"), 0.0)
        center = _safe_float(card.get("price_center"), anchor)
        confidence = _clip(_safe_float(card.get("confidence_score") or card.get("confidence"), 0.55), 0.0, 1.0)
        p_up = _safe_float(card.get("p_up"), 0.33)
        p_down = _safe_float(card.get("p_down"), 0.33)
        p_neutral = _safe_float(card.get("p_neutral"), 0.34)
        prob_up = _safe_float(card.get("prob_up"), 0.5)
        reasons: list[str] = []
        status = "通过"

        if quality < 0.35:
            status = "数据质量过低，降级为参考"
            reasons.append("data_quality_too_low")
            _soften_direction(card, 0.70, neutral_add=0.20)
            _compress_center(card, anchor, 0.35, "数据质量不足，价格中枢向实时价收敛")
            confidence *= 0.55
        elif quality < 0.50:
            reasons.append("data_quality_warning")
            _soften_direction(card, 0.30, neutral_add=0.08)
            confidence *= 0.80

        short_keys = {"next_5m", "next_15m", "next_30m", "next_hour", "h5m", "h15m", "h30m", "h1h"}
        if horizon_key in short_keys and not minute_data_available and not bool(card.get("validation_eligible")):
            reasons.append("minute_snapshot_insufficient_reference_only")
            card["reference_prediction"] = True
            card["validation_eligible"] = False
            card["validation_note"] = card.get("validation_note") or "分钟线/实时快照不足，短周期仅作参考，不计入真实命中率"
            _soften_direction(card, 0.25, neutral_add=0.05)
            confidence *= 0.86

        hit_rate = _profile_hit_rate(profile, horizon_key)
        if hit_rate is not None and hit_rate < 0.45:
            reasons.append("recent_direction_validation_weak")
            _soften_direction(card, 0.28, neutral_add=0.06)
            confidence *= 0.82

        # Strong direction and price path must not contradict each other.
        _normalize_probability_fields(card)
        prob_up = _safe_float(card.get("prob_up"), 0.5)
        p_neutral = _safe_float(card.get("p_neutral"), 0.34)
        center = _safe_float(card.get("price_center"), anchor)
        strong_up = prob_up >= 0.62 and p_neutral <= 0.42 and confidence >= 0.55
        strong_down = prob_up <= 0.38 and p_neutral <= 0.42 and confidence >= 0.55
        conflict = bool(anchor > 0 and ((strong_up and center < anchor) or (strong_down and center > anchor)))
        if conflict:
            reasons.append("direction_price_conflict")
            status = "方向与价格路径分歧，取消强方向"
            card["direction_price_conflict"] = True
            _soften_direction(card, 0.55, neutral_add=0.12)
            _compress_center(card, anchor, 0.45, "方向与价格中枢冲突，已降置信并收敛中枢")
            confidence *= 0.62

        _normalize_probability_fields(card)
        prob_up = _safe_float(card.get("prob_up"), 0.5)
        p_neutral = _safe_float(card.get("p_neutral"), 0.34)
        if abs(prob_up - 0.5) < 0.035 and p_neutral < 0.38:
            reasons.append("probability_edge_too_weak")
            _soften_direction(card, 0.15, neutral_add=0.08)

        _normalize_probability_fields(card)
        prob_up = _safe_float(card.get("prob_up"), 0.5)
        p_neutral = _safe_float(card.get("p_neutral"), 0.34)
        card["direction_key"] = _direction_key(prob_up, p_neutral)
        card["direction_label"] = _direction_label(prob_up, p_neutral)
        card["confidence_score"] = round(float(_clip(confidence, 0.0, 1.0)), 6)
        card["confidence"] = card["confidence_score"]
        card["direction_gate"] = {
            "status": status,
            "reasons": reasons or ["evidence_consistent"],
            "data_quality_score": quality,
            "minute_data_available": bool(minute_data_available),
            "recent_hit_rate": hit_rate,
            "raw_prob_up": card.get("raw_prob_up"),
            "gate_adjusted_prob_up": card.get("prob_up"),
        }
        card["probability_source"] = "方向优先模型 + 事件/数据质量闸门"
        card["display_drivers"] = [explain_driver(item) for item in card.get("core_drivers", [])]
        card["data_trust_badges"] = build_data_trust_badges(
            quality_score=quality,
            source_mode=source_mode,
            minute_data_available=minute_data_available,
        )
    return out
