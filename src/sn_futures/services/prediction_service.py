from __future__ import annotations

from typing import Any, Mapping

from .payload_utils import (
    DISCLAIMER,
    direction_zh,
    fmt_num,
    fmt_pct,
    fmt_price,
    is_observe_signal,
    label,
    remove_trade_points_for_observe,
    safe_float,
    sanitize_for_json,
    signal_zh,
)


LOW_QUALITY_THRESHOLD = 0.55


def _probabilities(card: Mapping[str, Any]) -> tuple[float | None, float | None, float | None]:
    p_up = safe_float(card.get("p_up", card.get("prob_up")))
    p_down = safe_float(card.get("p_down", card.get("prob_down")))
    p_neutral = safe_float(card.get("p_neutral", card.get("prob_neutral")))
    if p_neutral is None and p_up is not None and p_down is not None:
        p_neutral = max(0.0, 1.0 - p_up - p_down)
    return p_up, p_down, p_neutral


def _top_factors(card: Mapping[str, Any]) -> list[str]:
    factors: list[str] = []
    for key in ("top_factors", "display_drivers", "core_factors"):
        value = card.get(key)
        if isinstance(value, list):
            factors.extend(str(item) for item in value if item)
    candidates = card.get("direction_candidates")
    if isinstance(candidates, list):
        for row in candidates:
            if isinstance(row, Mapping):
                name = row.get("name") or row.get("factor") or "方向候选"
                direction = label(row.get("direction"), "待验证")
                score = row.get("score", row.get("strength", ""))
                factors.append(f"{name}：{direction}{f'，强度 {score}' if score not in {None, ''} else ''}")
    return factors[:6] or ["核心因子仍在积累，当前以价格、波动、量仓和事件证据综合判断。"]


def _event_basis(card: Mapping[str, Any]) -> list[str]:
    events: list[str] = []
    for key in ("top_bullish_events", "top_bearish_events", "top_volatility_events", "top_risk_events"):
        value = card.get(key)
        if isinstance(value, list):
            for item in value[:3]:
                if isinstance(item, Mapping):
                    title = item.get("title") or item.get("summary") or ""
                    if title:
                        events.append(str(title))
                elif item:
                    events.append(str(item))
    impact = card.get("news_policy_impact")
    if isinstance(impact, Mapping):
        summary = impact.get("summary")
        if isinstance(summary, str) and summary:
            events.append(summary)
        for key in ("top_bullish_events", "top_bearish_events", "top_volatility_events"):
            value = impact.get(key)
            if isinstance(value, list):
                for item in value[:2]:
                    if isinstance(item, Mapping) and item.get("title"):
                        events.append(str(item["title"]))
    return list(dict.fromkeys(events))[:5] or ["暂无高权重入模事件；事件因子不夸大解释。"]


def _path_guard(card: Mapping[str, Any]) -> str:
    diagnostics = card.get("path_diagnostics")
    if isinstance(diagnostics, Mapping):
        warnings = diagnostics.get("warnings")
        if isinstance(warnings, list) and warnings:
            return "；".join(label(item) for item in warnings[:4])
        return label(diagnostics.get("status"), "路径守门通过")
    return label(card.get("path_sanity_status") or card.get("path_guard_status"), "路径守门待验证")


def _risk_notes(card: Mapping[str, Any], data_quality: float) -> list[str]:
    notes = list(card.get("risk_notes") or []) if isinstance(card.get("risk_notes"), list) else []
    if data_quality < LOW_QUALITY_THRESHOLD:
        notes.insert(0, "数据质量不足，已降级为研究观察。")
    if card.get("direction_price_conflict"):
        notes.append("方向与价格路径存在分歧，已降低置信度。")
    notes.extend(
        [
            "预测基于历史数据和公开信息，可能出现延迟、误差或失效。",
            "强方向仅代表统计边际，不构成交易指令。",
        ]
    )
    return list(dict.fromkeys(str(item) for item in notes if item))[:6]


def _apply_data_quality_guard(card: dict[str, Any], data_quality: float) -> None:
    card["data_quality_score"] = data_quality
    card["数据质量"] = fmt_num(data_quality, 2)
    if data_quality >= LOW_QUALITY_THRESHOLD:
        return
    card["signal"] = "观望"
    card["direction"] = "neutral"
    card["direction_label"] = "观望"
    card["model_status_note"] = "数据质量不足，已降级为研究观察。"
    remove_trade_points_for_observe(card)


def normalize_prediction_card(card: Mapping[str, Any], *, horizon: str, horizon_label: str, data_quality: float) -> dict[str, Any]:
    normalized = dict(card)
    p_up, p_down, p_neutral = _probabilities(normalized)
    if p_up is not None:
        normalized["p_up"] = p_up
    if p_down is not None:
        normalized["p_down"] = p_down
    if p_neutral is not None:
        normalized["p_neutral"] = p_neutral
    _apply_data_quality_guard(normalized, data_quality)

    direction = direction_zh(normalized)
    signal = signal_zh(normalized)
    normalized["方向"] = direction
    normalized["信号"] = signal
    normalized["周期"] = horizon_label
    normalized["上涨概率"] = fmt_pct(normalized.get("p_up"))
    normalized["校准后概率"] = fmt_pct(normalized.get("calibrated_prob_up", normalized.get("p_up")))
    normalized["下跌概率"] = fmt_pct(normalized.get("p_down"))
    normalized["中性概率"] = fmt_pct(normalized.get("p_neutral"))
    normalized["预测收益"] = fmt_pct(normalized.get("expected_return", normalized.get("predicted_return")), 2)
    normalized["预测区间"] = f"{fmt_price(normalized.get('range_low', normalized.get('price_lower')))} - {fmt_price(normalized.get('range_high', normalized.get('price_upper')))}"
    normalized["置信度"] = fmt_num(normalized.get("confidence_score", normalized.get("confidence")), 1)
    normalized["模型状态"] = label(normalized.get("active_or_candidate_status", normalized.get("promotion_result")), "模型状态待验证")
    normalized["路径守门结果"] = _path_guard(normalized)
    normalized["核心因子"] = _top_factors(normalized)
    normalized["事件依据"] = _event_basis(normalized)
    normalized["风险提示"] = _risk_notes(normalized, data_quality)
    normalized["回测摘要"] = normalized.get("backtest_summary") or {
        "方向命中率": fmt_pct(normalized.get("backtest_direction_accuracy")),
        "强信号命中率": fmt_pct(normalized.get("strong_signal_accuracy")),
        "概率误差(Brier)": fmt_num(normalized.get("brier_score"), 3),
        "校准误差(ECE)": fmt_num(normalized.get("expected_calibration_error"), 3),
    }
    normalized["决策说明"] = {
        "摘要": f"{horizon_label}：当前输出{direction}，信号为{signal}；上涨概率{normalized['上涨概率']}，下跌概率{normalized['下跌概率']}。",
        "方向依据": normalized["核心因子"],
        "事件依据": normalized["事件依据"],
        "路径说明": normalized["路径守门结果"],
        "治理说明": normalized["模型状态"],
    }
    normalized["display_tags"] = normalized.get("display_tags") or [
        {"label": "方向", "value": direction, "tone": "bull" if direction == "上涨" else "bear" if direction == "下跌" else "neutral"},
        {"label": "信号", "value": signal, "tone": "info"},
        {"label": "上涨概率", "value": normalized["上涨概率"], "tone": "bull"},
        {"label": "下跌概率", "value": normalized["下跌概率"], "tone": "bear"},
        {"label": "预测区间", "value": normalized["预测区间"], "tone": "info"},
        {"label": "数据质量", "value": normalized["数据质量"], "tone": "warning" if data_quality < LOW_QUALITY_THRESHOLD else "info"},
        {"label": "模型状态", "value": normalized["模型状态"], "tone": "info"},
        {"label": "路径守门", "value": normalized["路径守门结果"], "tone": "info"},
    ]
    if is_observe_signal(normalized):
        remove_trade_points_for_observe(normalized)
    return sanitize_for_json(normalized)


def integrate_live_prediction_payload(payload: Mapping[str, Any], *, horizon_labels: Mapping[str, str]) -> dict[str, Any]:
    out = dict(payload)
    watermark = out.get("data_watermark") if isinstance(out.get("data_watermark"), Mapping) else {}
    data_quality = safe_float(watermark.get("quality_score"), 0.0) or 0.0
    cards = out.get("cards") if isinstance(out.get("cards"), Mapping) else {}
    normalized_cards: dict[str, Any] = {}
    for horizon, card in cards.items():
        if not isinstance(card, Mapping):
            continue
        normalized_cards[str(horizon)] = normalize_prediction_card(
            card,
            horizon=str(horizon),
            horizon_label=horizon_labels.get(str(horizon), str(horizon)),
            data_quality=data_quality,
        )
    out["cards"] = normalized_cards
    out["数据质量"] = fmt_num(data_quality, 2)
    out["合规声明"] = DISCLAIMER
    return sanitize_for_json(out)
