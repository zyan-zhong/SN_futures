from __future__ import annotations

from typing import Any, Mapping


NEUTRAL_TARGET_BANDS: dict[str, tuple[float, float]] = {
    "next_5m": (0.30, 0.58),
    "next_15m": (0.25, 0.55),
    "next_30m": (0.20, 0.52),
    "next_hour": (0.18, 0.50),
    "tomorrow": (0.12, 0.45),
    "one_to_two_weeks": (0.10, 0.40),
    "one_to_three_months": (0.08, 0.35),
}


def _safe_prob(value: Any, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except Exception:
        return default
    if numeric < 0:
        return 0.0
    if numeric > 1:
        return 1.0
    return numeric


def _card_neutral_probability(card: Mapping[str, Any]) -> float:
    if "p_neutral" in card:
        return _safe_prob(card.get("p_neutral"), 0.0)
    if "prob_neutral" in card:
        return _safe_prob(card.get("prob_neutral"), 0.0)
    up = _safe_prob(card.get("prob_up", card.get("p_up")), 0.5)
    down = _safe_prob(card.get("prob_down", card.get("p_down")), 0.5)
    return max(0.0, min(1.0, 1.0 - up - down))


def audit_neutral_rates(live_cards: Mapping[str, Any]) -> dict[str, Any]:
    """Check neutral-rate health without encouraging hard threshold hacking.

    The audit is deliberately advisory.  A high neutral rate should trigger
    feature, edge-model and event-chain review; it should not be "fixed" by
    simply lowering the neutral threshold.
    """

    rows: list[dict[str, Any]] = []
    severe = False
    warning = False
    for horizon, (low, high) in NEUTRAL_TARGET_BANDS.items():
        raw_card = live_cards.get(horizon, {}) if isinstance(live_cards, Mapping) else {}
        card = raw_card if isinstance(raw_card, Mapping) else {}
        neutral = _card_neutral_probability(card)
        if neutral > high + 0.25 or neutral < max(0.0, low - 0.20):
            severity = "red"
            severe = True
        elif neutral > high or neutral < low:
            severity = "yellow"
            warning = True
        else:
            severity = "normal"
        if neutral > high:
            reason = "中性率偏高：优先检查 edge 模型、事件入模、数据新鲜度与概率校准，禁止只靠降阈值硬压中性。"
        elif neutral < low:
            reason = "中性率偏低：检查是否过度输出弱方向，避免用低置信方向制造表面可用性。"
        else:
            reason = "中性率位于目标带内。"
        rows.append(
            {
                "horizon": horizon,
                "p_neutral": round(neutral, 6),
                "target_low": low,
                "target_high": high,
                "ok": severity == "normal",
                "severity": severity,
                "reason": reason,
            }
        )

    return {
        "ok": not severe,
        "status": "passed" if not severe else "failed",
        "severity": "red" if severe else ("yellow" if warning else "normal"),
        "summary": "中性率审计完成；异常项用于触发模型诊断，不代表可以简单调低阈值。",
        "rows": rows,
        "target_bands": {key: {"low": val[0], "high": val[1]} for key, val in NEUTRAL_TARGET_BANDS.items()},
    }
