from __future__ import annotations

from typing import Any


def compute_expected_edge(
    calibrated_prob: float,
    avg_win: float,
    avg_loss: float,
    estimated_cost: float = 0.0,
) -> float:
    p = max(0.0, min(1.0, float(calibrated_prob)))
    return float(p * abs(avg_win) - (1.0 - p) * abs(avg_loss) - abs(float(estimated_cost)))


def confidence_from_probability(prob_up: float, data_quality_score: float = 1.0) -> float:
    edge_distance = abs(float(prob_up) - 0.5) * 2.0
    quality = max(0.0, min(1.0, float(data_quality_score)))
    return float(max(0.0, min(100.0, 100.0 * edge_distance * quality)))


def signal_strength(prob_up: float, confidence_score: float, trade_edge: float) -> str:
    if trade_edge <= 0 or confidence_score < 20:
        return "abstain"
    if prob_up >= 0.62 and confidence_score >= 55:
        return "strong_up"
    if prob_up >= 0.55:
        return "weak_up"
    if prob_up <= 0.38 and confidence_score >= 55:
        return "strong_down"
    if prob_up <= 0.45:
        return "weak_down"
    return "neutral"


def selective_signal(
    *,
    calibrated_prob_up: float,
    trade_edge: float,
    data_quality_score: float,
    model_health: str = "ok",
    no_trade_band: tuple[float, float] = (0.45, 0.55),
    min_data_quality: float = 0.45,
) -> dict[str, Any]:
    p = max(0.0, min(1.0, float(calibrated_prob_up)))
    reasons: list[str] = []
    signal = "观望"
    direction = "neutral"
    if no_trade_band[0] <= p <= no_trade_band[1]:
        reasons.append("方向概率处于 45%-55% 中性区间。")
    if trade_edge <= 0:
        reasons.append("扣除估算成本后期望边际不为正。")
    if data_quality_score < min_data_quality:
        reasons.append("数据质量评分低于阈值。")
    if str(model_health).lower() in {"failed", "fail", "error"}:
        reasons.append("模型健康状态未通过。")
    if not reasons:
        if p > no_trade_band[1]:
            signal = "多头研究观察"
            direction = "up"
        else:
            signal = "空头研究观察"
            direction = "down"
        reasons.append("方向概率、期望边际、数据质量和模型健康均通过筛选。")
    return {"signal": signal, "direction": direction, "reason": "；".join(reasons)}

