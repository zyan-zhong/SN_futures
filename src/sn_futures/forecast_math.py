from __future__ import annotations

import numpy as np


def _safe_logit(prob: float) -> float:
    p = float(np.clip(prob, 1e-4, 1 - 1e-4))
    return float(np.log(p / (1.0 - p)))


def _safe_sigmoid(value: float) -> float:
    clipped = float(np.clip(value, -20.0, 20.0))
    return float(1.0 / (1.0 + np.exp(-clipped)))


def cohere_directional_forecast(
    expected_return: float,
    prob_up: float,
    volatility: float,
) -> tuple[float, float]:
    exp_ret = float(expected_return) if np.isfinite(expected_return) else 0.0
    prob = float(prob_up) if np.isfinite(prob_up) else 0.5
    prob = float(np.clip(prob, 0.01, 0.99))
    vol = max(float(volatility) if np.isfinite(volatility) else 0.01, 1e-4)
    return_prob = _safe_sigmoid((exp_ret / max(vol * 0.95, 1e-4)) * 1.65)
    disagreement = abs((prob - 0.5) - (return_prob - 0.5))
    prob_weight = 0.58 if disagreement >= 0.22 else 0.64
    coherent_logit = prob_weight * _safe_logit(prob) + (1.0 - prob_weight) * _safe_logit(return_prob)
    coherent_prob = float(np.clip(_safe_sigmoid(coherent_logit), 0.02, 0.98))

    edge = coherent_prob - 0.5
    prob_implied_return = float(np.tanh(edge * 3.2) * vol * 1.85)
    return_weight = 0.52 if disagreement >= 0.22 else 0.58
    coherent_return = return_weight * exp_ret + (1.0 - return_weight) * prob_implied_return

    if coherent_prob >= 0.55 and coherent_return < 0:
        coherent_return = abs(coherent_return) * 0.20 + abs(prob_implied_return) * 0.80
    elif coherent_prob <= 0.45 and coherent_return > 0:
        coherent_return = -(abs(coherent_return) * 0.20 + abs(prob_implied_return) * 0.80)
    elif 0.45 < coherent_prob < 0.55:
        coherent_return *= 0.22

    max_magnitude = max(abs(exp_ret) * 1.20, vol * 2.60, 0.0020)
    coherent_return = float(np.clip(coherent_return, -max_magnitude, max_magnitude))
    return coherent_return, coherent_prob
