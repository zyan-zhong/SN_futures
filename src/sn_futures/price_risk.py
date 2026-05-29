from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any

import numpy as np

from .forecast_math import cohere_directional_forecast


@dataclass(frozen=True)
class HorizonRiskSpec:
    horizon_key: str
    label: str
    target_days: int
    max_center_offset: float
    min_half_width: float
    max_half_width: float
    volatility_multiplier: float
    probability_decay: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


HORIZON_RISK_SPECS: dict[str, HorizonRiskSpec] = {
    "next_5m": HorizonRiskSpec(
        horizon_key="next_5m",
        label="未来5分钟",
        target_days=0,
        max_center_offset=0.0030,
        min_half_width=0.0006,
        max_half_width=0.0035,
        volatility_multiplier=0.55,
        probability_decay=0.38,
    ),
    "next_15m": HorizonRiskSpec(
        horizon_key="next_15m",
        label="未来15分钟",
        target_days=0,
        max_center_offset=0.0050,
        min_half_width=0.0010,
        max_half_width=0.0060,
        volatility_multiplier=0.70,
        probability_decay=0.45,
    ),
    "next_30m": HorizonRiskSpec(
        horizon_key="next_30m",
        label="未来30分钟",
        target_days=0,
        max_center_offset=0.0065,
        min_half_width=0.0015,
        max_half_width=0.0085,
        volatility_multiplier=0.85,
        probability_decay=0.50,
    ),
    "next_hour": HorizonRiskSpec(
        horizon_key="next_hour",
        label="下一小时",
        target_days=0,
        max_center_offset=0.0095,
        min_half_width=0.0025,
        max_half_width=0.014,
        volatility_multiplier=1.05,
        probability_decay=0.55,
    ),
    "tomorrow": HorizonRiskSpec(
        horizon_key="tomorrow",
        label="下一交易日",
        target_days=1,
        max_center_offset=0.028,
        min_half_width=0.005,
        max_half_width=0.038,
        volatility_multiplier=1.18,
        probability_decay=0.86,
    ),
    "one_to_two_weeks": HorizonRiskSpec(
        horizon_key="one_to_two_weeks",
        label="未来1-2周",
        target_days=10,
        max_center_offset=0.045,
        min_half_width=0.018,
        max_half_width=0.055,
        volatility_multiplier=0.92,
        probability_decay=0.72,
    ),
    "one_to_three_months": HorizonRiskSpec(
        horizon_key="one_to_three_months",
        label="未来1-3个月",
        target_days=60,
        max_center_offset=0.065,
        min_half_width=0.030,
        max_half_width=0.075,
        volatility_multiplier=0.78,
        probability_decay=0.58,
    ),
}


def get_horizon_spec(horizon_key: str) -> HorizonRiskSpec:
    return HORIZON_RISK_SPECS.get(str(horizon_key), HORIZON_RISK_SPECS["tomorrow"])


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except Exception:
        return default
    return numeric if np.isfinite(numeric) else default


def _probability_from_return(expected_return: float, volatility: float, prior_prob: float, spec: HorizonRiskSpec) -> float:
    implied = 0.5 + 0.5 * float(np.tanh(expected_return / max(volatility * 1.55, 1e-4)))
    blended = 0.5 + (prior_prob - 0.5) * spec.probability_decay
    return float(np.clip(0.52 * implied + 0.48 * blended, 0.03, 0.97))


def apply_realistic_price_gate(card: dict[str, Any]) -> dict[str, Any]:
    """Apply a single, shared price realism policy for live cards and chart rows.

    The gate deliberately favors credible ranges over dramatic-looking forecasts.
    It does not fabricate accuracy; it records every compression reason for the UI.
    """
    if not isinstance(card, dict):
        return card
    horizon_key = str(card.get("horizon_key") or card.get("horizon") or "tomorrow")
    spec = get_horizon_spec(horizon_key)
    anchor = _safe_float(card.get("anchor_close", card.get("close", card.get("asof_price", 0.0))), 0.0)
    provisional_center = _safe_float(card.get("price_center", card.get("pred_center", 0.0)), 0.0)
    original_center = provisional_center if provisional_center > 0 else anchor
    if anchor <= 0 and original_center > 0:
        anchor = original_center
    if anchor <= 0:
        return card

    original_center = _safe_float(card.get("price_center", card.get("pred_center", anchor)), anchor)
    original_low = _safe_float(card.get("range_low", card.get("pred_low", original_center)), original_center)
    original_high = _safe_float(card.get("range_high", card.get("pred_high", original_center)), original_center)
    raw_expected = _safe_float(card.get("expected_return", (original_center / anchor) - 1.0), 0.0)
    raw_prob = _safe_float(card.get("prob_up", card.get("raw_prob_up", 0.5)), 0.5)
    volatility = max(_safe_float(card.get("volatility", 0.012), 0.012), 1e-4)

    coherent_return, coherent_prob = cohere_directional_forecast(raw_expected, raw_prob, volatility)
    clipped_return = float(np.clip(coherent_return, -spec.max_center_offset, spec.max_center_offset))
    center = anchor * (1.0 + clipped_return)

    original_half_pct = abs(original_high - original_low) / max(anchor * 2.0, 1e-9)
    vol_half_pct = volatility * spec.volatility_multiplier
    half_width_pct = float(np.clip(max(original_half_pct, vol_half_pct, spec.min_half_width), spec.min_half_width, spec.max_half_width))
    news_impact = card.get("news_policy_impact", {}) if isinstance(card.get("news_policy_impact"), dict) else {}
    news_weight = _safe_float(news_impact.get("confidence_weight"), 0.0)
    news_sentiment = abs(_safe_float(news_impact.get("weighted_sentiment"), 0.0))
    has_major_event = bool(news_weight >= 0.45 or news_sentiment >= 0.35)
    shrink_factor = 1.0
    if not has_major_event:
        if horizon_key in {"next_5m", "next_15m", "next_30m", "next_hour"}:
            shrink_factor = 0.88
        elif horizon_key == "tomorrow":
            shrink_factor = 0.84
        else:
            shrink_factor = 0.78
    if shrink_factor < 1.0:
        half_width_pct = float(np.clip(half_width_pct * shrink_factor, spec.min_half_width, spec.max_half_width))
    low = max(0.0, center - anchor * half_width_pct)
    high = max(low, center + anchor * half_width_pct)

    adjusted_prob = _probability_from_return(clipped_return, max(volatility, half_width_pct / 2.0), coherent_prob, spec)
    reasons: list[str] = []
    if abs(clipped_return - coherent_return) > 1e-8:
        reasons.append(f"{spec.label}中枢偏移超过{spec.max_center_offset:.1%}，已按真实风险上限压缩")
    if original_half_pct > spec.max_half_width + 1e-8:
        reasons.append(f"{spec.label}区间宽度超过{spec.max_half_width:.1%}，已去除图表层二次放大")
    if shrink_factor < 1.0:
        reasons.append("无重大新闻/政策事件确认，区间按稳健模式收窄")
    if abs((adjusted_prob - 0.5) - (raw_prob - 0.5)) > 0.08:
        reasons.append("方向概率已按价格中枢一致性重新校准")
    if not reasons:
        reasons.append("价格区间通过现实校准，未触发压缩")

    card["anchor_close"] = anchor
    card["expected_return"] = clipped_return
    card["center_offset_pct"] = clipped_return
    card["price_center"] = center
    card["range_low"] = low
    card["range_high"] = high
    card["prob_up"] = adjusted_prob
    card["prob_down"] = 1.0 - adjusted_prob
    card["realistic_price_gate"] = {
        "status": "compressed" if len(reasons) and "通过" not in reasons[0] else "passed",
        "reasons": reasons,
        "anchor_price": anchor,
        "original_center": original_center,
        "original_low": original_low,
        "original_high": original_high,
        "adjusted_center": center,
        "adjusted_low": low,
        "adjusted_high": high,
        "center_cap_pct": spec.max_center_offset,
        "half_width_cap_pct": spec.max_half_width,
        "half_width_pct": half_width_pct,
        "range_shrink_factor": shrink_factor,
        "major_event_used": has_major_event,
        "policy": spec.to_dict(),
    }
    card["range_source"] = card.get("range_source") or "历史波动率 + ATR + 近期兑现误差 + 新闻事件权重"
    return card


def apply_realistic_price_gates(payload: dict[str, Any]) -> dict[str, Any]:
    cards = payload.get("cards", {}) if isinstance(payload.get("cards"), dict) else {}
    for key, card in cards.items():
        if isinstance(card, dict):
            card.setdefault("horizon_key", str(key))
            apply_realistic_price_gate(card)
    payload["cards"] = cards
    return payload
