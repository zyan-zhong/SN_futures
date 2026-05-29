from __future__ import annotations

from typing import Any, Mapping


DISCLAIMER = "本模块仅用于持仓风险情景化投研参考，不构成任何投资建议或交易指令。"
BANNED_CERTAINTY_TERMS = ("必须买入", "必须卖出", "保证上涨", "保证下跌", "稳赚", "保本")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _dominant_card(live_payload: Mapping[str, Any]) -> dict[str, Any]:
    cards = live_payload.get("cards", {}) if isinstance(live_payload.get("cards", {}), Mapping) else {}
    for key in ("tomorrow", "next_hour", "one_to_two_weeks"):
        card = cards.get(key)
        if isinstance(card, Mapping):
            return dict(card)
    return {}


def _risk_band(latest_price: float, width_pct: float) -> tuple[float, float]:
    return (round(latest_price * (1 - width_pct), 2), round(latest_price * (1 + width_pct), 2))


def evaluate_position_scenario(user_position: Mapping[str, Any], live_payload: Mapping[str, Any]) -> dict[str, Any]:
    """Generate compliant, non-prescriptive position-aware research zones."""

    card = _dominant_card(live_payload)
    latest = _safe_float(card.get("anchor_price") or card.get("latest_price") or card.get("price_center"), 0.0)
    if latest <= 0:
        latest = _safe_float(user_position.get("current_price") or user_position.get("avg_price"), 0.0)
    p_up = _safe_float(card.get("prob_up") or card.get("p_up"), 0.5)
    p_down = _safe_float(card.get("prob_down") or card.get("p_down"), 0.5)
    p_neutral = _safe_float(card.get("p_neutral") or card.get("prob_neutral"), max(0.0, 1 - p_up - p_down))
    confidence = _safe_float(card.get("confidence_score") or card.get("confidence"), 50.0)
    data_quality = _safe_float(card.get("data_quality_score"), 0.5)
    direction = str(card.get("direction") or card.get("direction_label") or "neutral")
    model_uncertain = confidence < 65 or data_quality < 0.55 or p_neutral > 0.55

    base_width = 0.006 if confidence >= 75 and data_quality >= 0.7 else 0.011
    wider_width = base_width * 1.8
    zones = [
        {
            "name": "低风险试探区",
            "price_range": _risk_band(latest, base_width),
            "basis": "仅在多周期方向、数据新鲜度和事件证据较一致时具备研究参考意义。",
            "risk_note": "若数据延迟、方向分歧或事件链路异常，应降级为观察。",
        },
        {
            "name": "加仓触发区",
            "price_range": _risk_band(latest, base_width * 0.7),
            "basis": "需要方向概率边际、strong signal 历史表现和事件证据共同支持。",
            "risk_note": "本区间不是买入指令；仅用于预案观察和风控测算。",
        },
        {
            "name": "减仓观察区",
            "price_range": _risk_band(latest, wider_width),
            "basis": "当持仓方向与模型方向冲突、置信度下降或数据质量变差时进入重点观察。",
            "risk_note": "用于提示风险暴露变化，不构成平仓建议。",
        },
        {
            "name": "止损失效区",
            "price_range": _risk_band(latest, wider_width * 1.35),
            "basis": "以用户最大允许亏损、波动率和预测区间外沿综合估算。",
            "risk_note": "该区间用于风险预警，不代表系统可以保证损失上限。",
        },
        {
            "name": "仅观望区",
            "price_range": _risk_band(latest, wider_width * 2.0),
            "basis": "当方向优势不足、新闻政策链路失败、数据 stale 或模型冲突时优先采用。",
            "risk_note": "不确定性较高时，系统只给投研观察提示。",
        },
    ]
    if model_uncertain:
        headline = "当前模型不确定性较高，持仓情景以观察和风险暴露核查为主。"
    elif p_up > p_down:
        headline = "当前方向证据偏多，但仍需结合持仓周期、风险预算和事件变化独立判断。"
    elif p_down > p_up:
        headline = "当前方向证据偏空，但仍需结合持仓周期、风险预算和事件变化独立判断。"
    else:
        headline = "当前方向分歧较大，建议把重点放在数据新鲜度和事件证据验证。"

    payload = {
        "ok": True,
        "headline": headline,
        "latest_price": latest,
        "model_direction": direction,
        "p_up": round(p_up, 6),
        "p_down": round(p_down, 6),
        "p_neutral": round(p_neutral, 6),
        "confidence_score": round(confidence, 3),
        "data_quality_score": round(data_quality, 3),
        "zones": zones,
        "uncertainty_flags": {
            "model_uncertain": model_uncertain,
            "low_confidence": confidence < 65,
            "low_data_quality": data_quality < 0.55,
            "high_neutral_probability": p_neutral > 0.55,
        },
        "user_inputs_echo": {
            "position_direction": user_position.get("position_direction", ""),
            "quantity": user_position.get("quantity", ""),
            "avg_price": user_position.get("avg_price", ""),
            "max_loss": user_position.get("max_loss", ""),
            "holding_horizon": user_position.get("holding_horizon", ""),
        },
        "disclaimer": DISCLAIMER,
    }
    text_blob = str(payload)
    for term in BANNED_CERTAINTY_TERMS:
        if term in text_blob:
            raise ValueError(f"position scenario contains prohibited certainty term: {term}")
    return payload
