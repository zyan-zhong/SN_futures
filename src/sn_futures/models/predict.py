from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from .ensemble import compute_expected_edge, confidence_from_probability, selective_signal, signal_strength
from .regime_models import predict_regime_ensemble
from .train import HorizonModelBundle


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        out = float(value)
    except Exception:
        return default
    return out if np.isfinite(out) else default


def _top_factors(bundle: HorizonModelBundle, limit: int = 5) -> list[dict[str, float | str]]:
    return list(bundle.regime_ensemble.global_model.feature_importance[:limit])


def predict_horizon(
    bundle: HorizonModelBundle,
    row: pd.Series | pd.DataFrame,
    *,
    current_price: float | None = None,
    data_quality_score: float = 1.0,
    model_health: str = "ok",
    avg_win: float | None = None,
    avg_loss: float | None = None,
    estimated_cost: float = 0.0008,
    volatility_col: str = "realized_vol_5d",
) -> dict[str, Any]:
    frame = row.to_frame().T if isinstance(row, pd.Series) else row.copy()
    current = _safe_float(current_price, _safe_float(frame.iloc[0].get("close"), 0.0))
    regime_pred = predict_regime_ensemble(bundle.regime_ensemble, frame.iloc[0])
    raw_prob = float(regime_pred["ensemble_prediction"]["prob_up"])
    calibrated_prob = bundle.calibrator.transform_one(raw_prob)
    expected_return = float(regime_pred["ensemble_prediction"]["expected_return"])
    expected_volatility = abs(_safe_float(frame.iloc[0].get(volatility_col), abs(expected_return) * 2.0 + 0.005))
    avg_win_value = abs(float(avg_win)) if avg_win is not None else max(abs(expected_return) * 1.35, expected_volatility * 0.55, 0.003)
    avg_loss_value = abs(float(avg_loss)) if avg_loss is not None else max(abs(expected_return) * 1.10, expected_volatility * 0.50, 0.003)
    edge = compute_expected_edge(calibrated_prob, avg_win_value, avg_loss_value, estimated_cost)
    confidence = confidence_from_probability(calibrated_prob, data_quality_score)
    selected = selective_signal(
        calibrated_prob_up=calibrated_prob,
        trade_edge=edge,
        data_quality_score=data_quality_score,
        model_health=model_health,
    )
    strength = signal_strength(calibrated_prob, confidence, edge)
    if selected["signal"] == "观望":
        strength = "neutral" if strength != "abstain" else strength

    center = current * (1.0 + expected_return) if current > 0 else expected_return
    half_width = max(current * expected_volatility * 1.28, current * 0.002 if current > 0 else expected_volatility)
    low = center - half_width
    high = center + half_width
    direction = selected["direction"]
    risk_notes = []
    if data_quality_score < 0.45:
        risk_notes.append("数据质量较低，已默认观望。")
    if edge <= 0:
        risk_notes.append("扣除成本后期望边际不足。")
    if model_health.lower() in {"failed", "fail", "error"}:
        risk_notes.append("模型健康状态未通过。")
    if not risk_notes:
        risk_notes.append("预测仍可能失效，仅供量化投研参考。")

    return {
        "horizon": bundle.horizon,
        "direction": direction,
        "raw_prob_up": raw_prob,
        "calibrated_prob_up": calibrated_prob,
        "expected_return": expected_return,
        "expected_volatility": expected_volatility,
        "expected_drawdown": avg_loss_value,
        "estimated_cost": float(abs(estimated_cost)),
        "predicted_range": [float(low), float(high)],
        "trade_edge": edge,
        "confidence_score": confidence,
        "signal_strength": strength,
        "signal": selected["signal"],
        "reason": selected["reason"],
        "top_factors": _top_factors(bundle),
        "risk_notes": risk_notes,
        "global_prediction": regime_pred["global_prediction"],
        "regime_prediction": regime_pred["regime_prediction"],
        "ensemble_prediction": regime_pred["ensemble_prediction"],
        "regime_used": regime_pred["regime_used"],
        "fallback_reason": regime_pred["fallback_reason"],
        "calibration_method": bundle.calibrator.method,
        "brier_score": bundle.calibrator.brier_score,
        "calibration_error": bundle.calibrator.calibration_error,
    }

