from __future__ import annotations

from typing import Any, Mapping

from .payload_utils import DISCLAIMER, direction_zh, safe_float, sanitize_for_json


CONTRACT_MULTIPLIER = 1.0
DEFAULT_MARGIN_RATE = 0.12


def build_position_scenario(user_position: Mapping[str, Any], live_payload: Mapping[str, Any]) -> dict[str, Any]:
    cards = live_payload.get("cards", {}) if isinstance(live_payload.get("cards"), Mapping) else {}
    horizon = str(user_position.get("holding_horizon") or user_position.get("plan_horizon") or "tomorrow")
    card = cards.get(horizon) if isinstance(cards.get(horizon), Mapping) else next((item for item in cards.values() if isinstance(item, Mapping)), {})
    latest = (
        safe_float(card.get("anchor_price"))
        or safe_float(card.get("latest_price"))
        or safe_float(card.get("price_center"))
        or safe_float(user_position.get("current_price"))
        or safe_float(user_position.get("avg_price"))
        or 0.0
    )
    quantity = abs(safe_float(user_position.get("quantity"), 0.0) or 0.0)
    avg_price = safe_float(user_position.get("avg_price"), latest) or latest
    equity = safe_float(user_position.get("account_equity"), 0.0) or 0.0
    max_loss = safe_float(user_position.get("max_loss"), 0.0) or 0.0
    p_up = safe_float(card.get("p_up", card.get("prob_up")), 0.5) or 0.5
    p_down = safe_float(card.get("p_down", card.get("prob_down")), 0.5) or 0.5
    p_neutral = safe_float(card.get("p_neutral", card.get("prob_neutral")), max(0.0, 1 - p_up - p_down)) or 0.0
    confidence = safe_float(card.get("confidence_score", card.get("confidence")), 50.0) or 50.0
    data_quality = safe_float(card.get("data_quality_score"), 0.5) or 0.5
    direction = direction_zh(card)
    notional = latest * quantity * CONTRACT_MULTIPLIER
    margin_required = notional * DEFAULT_MARGIN_RATE
    base_vol = max(0.006, abs((safe_float(card.get("range_high"), latest) or latest) - (safe_float(card.get("range_low"), latest) or latest)) / max(latest, 1) / 4)
    var_95 = notional * min(max(base_vol * 1.65, 0.006), 0.08)
    stress_var = var_95 * 2.2
    max_loss_ratio = max_loss / equity if equity > 0 else None
    model_uncertain = data_quality < 0.55 or confidence < 60 or p_neutral > 0.58

    observation_zones = [
        {
            "名称": "低风险试探区",
            "区间": [round(latest * (1 - base_vol), 2), round(latest * (1 + base_vol), 2)],
            "依据": "方向概率、数据质量和事件证据较一致时才具备研究观察意义。",
        },
        {
            "名称": "加仓观察区",
            "区间": [round(latest * (1 - base_vol * 0.65), 2), round(latest * (1 + base_vol * 0.65), 2)],
            "依据": "需要多周期共振、事件支持和模型置信度共同改善。",
        },
        {
            "名称": "减仓观察区",
            "区间": [round(latest * (1 - base_vol * 1.8), 2), round(latest * (1 + base_vol * 1.8), 2)],
            "依据": "当持仓方向与模型方向冲突、数据质量下降或事件风险抬升时重点观察。",
        },
    ]
    risk_zones = [
        {
            "名称": "止损失效区",
            "区间": [round(avg_price - stress_var / max(quantity * CONTRACT_MULTIPLIER, 1), 2), round(avg_price + stress_var / max(quantity * CONTRACT_MULTIPLIER, 1), 2)],
            "说明": "用于压力情景测算，不代表保证损失上限。",
        },
        {
            "名称": "仅观望区",
            "区间": [round(latest * (1 - base_vol * 2.6), 2), round(latest * (1 + base_vol * 2.6), 2)],
            "说明": "方向优势不足、数据 stale 或模型冲突时优先采用。",
        },
    ]
    return sanitize_for_json(
        {
            "ok": True,
            "名义敞口": round(notional, 2),
            "保证金占用": round(margin_required, 2),
            "VaR 95": round(var_95, 2),
            "压力 VaR": round(stress_var, 2),
            "最大可承受亏损占比": max_loss_ratio,
            "观察区": observation_zones,
            "风险区": risk_zones,
            "周期共振": f"计划周期 {horizon}，当前模型方向为{direction}；上涨概率 {p_up:.1%}，下跌概率 {p_down:.1%}。",
            "事件依据": card.get("事件依据") or ["暂无高权重入模事件，按保守口径观察。"],
            "不确定性提示": [
                "模型不确定性较高，持仓情景以风险暴露核查为主。" if model_uncertain else "模型证据相对清晰，但仍需结合个人风险预算独立判断。",
                "免费公开数据可能延迟或缺失。",
                "本模块不输出确定性买卖建议。",
            ],
            "headline": "持仓情景已按当前模型、数据质量和风险预算生成观察区。",
            "latest_price": latest,
            "model_direction": direction,
            "p_up": p_up,
            "p_down": p_down,
            "p_neutral": p_neutral,
            "confidence_score": confidence,
            "data_quality_score": data_quality,
            "zones": observation_zones + risk_zones,
            "disclaimer": DISCLAIMER,
        }
    )
