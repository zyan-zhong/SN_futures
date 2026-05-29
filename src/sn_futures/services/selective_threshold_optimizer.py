from __future__ import annotations

from typing import Any, Iterable

import numpy as np

from ..api.json_utils import sanitize_for_json


def _as_array(values: Iterable[Any]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    arr = np.where(np.isfinite(arr), arr, np.nan)
    return arr


def _max_drawdown(returns: np.ndarray) -> float:
    if returns.size == 0:
        return 0.0
    equity = np.cumsum(returns)
    peak = np.maximum.accumulate(equity)
    return float(np.min(equity - peak))


def _coverage_metrics(
    calibrated_prob: np.ndarray,
    realized_return: np.ndarray,
    realized_direction: np.ndarray,
    confidence: np.ndarray,
    coverage: float,
    cost: float,
) -> dict[str, Any]:
    valid = np.isfinite(calibrated_prob) & np.isfinite(realized_return) & np.isfinite(realized_direction) & np.isfinite(confidence)
    n_valid = int(valid.sum())
    if n_valid == 0:
        return {
            "coverage": float(coverage),
            "sample_count": 0,
            "accuracy_at_coverage": None,
            "expectancy_at_coverage": None,
            "drawdown_at_coverage": None,
            "min_confidence": None,
        }
    target = max(1, int(np.ceil(n_valid * float(coverage))))
    order = np.argsort(-confidence[valid])
    valid_idx = np.where(valid)[0][order[:target]]
    selected_prob = calibrated_prob[valid_idx]
    pred_direction = np.where(selected_prob >= 0.5, 1, -1)
    actual_direction = np.where(realized_direction[valid_idx] > 0, 1, -1)
    selected_returns = pred_direction * realized_return[valid_idx] - float(cost)
    return {
        "coverage": float(len(valid_idx) / n_valid),
        "target_coverage": float(coverage),
        "sample_count": int(len(valid_idx)),
        "accuracy_at_coverage": float((pred_direction == actual_direction).mean()) if len(valid_idx) else None,
        "expectancy_at_coverage": float(selected_returns.mean()) if len(valid_idx) else None,
        "drawdown_at_coverage": _max_drawdown(selected_returns),
        "min_confidence": float(np.nanmin(confidence[valid_idx])) if len(valid_idx) else None,
    }


def optimize_selective_thresholds(
    *,
    calibrated_prob: Iterable[Any],
    expected_return: Iterable[Any],
    realized_return: Iterable[Any],
    realized_direction: Iterable[Any],
    cost: float = 0.0002,
    coverages: Iterable[float] = (0.10, 0.20),
) -> dict[str, Any]:
    """Optimize selection thresholds on validation predictions only."""

    prob = _as_array(calibrated_prob)
    exp_ret = _as_array(expected_return)
    ret = _as_array(realized_return)
    direction = _as_array(realized_direction)
    n = min(len(prob), len(exp_ret), len(ret), len(direction))
    prob, exp_ret, ret, direction = prob[:n], exp_ret[:n], ret[:n], direction[:n]

    confidence = np.abs(prob - 0.5) * 2.0
    edge = prob * np.maximum(exp_ret, 0.0) - (1.0 - prob) * np.maximum(-exp_ret, 0.0) - float(cost)
    valid_edge = edge[np.isfinite(edge)]
    valid_conf = confidence[np.isfinite(confidence)]
    min_edge = float(np.nanpercentile(valid_edge, 70)) if valid_edge.size else 0.0
    min_confidence = float(np.nanpercentile(valid_conf, 80)) if valid_conf.size else 0.0
    prob_threshold_up = float(0.5 + min_confidence / 2.0)
    prob_threshold_down = float(0.5 - min_confidence / 2.0)

    by_coverage = {
        f"top_{int(float(cov) * 100)}pct": _coverage_metrics(prob, ret, direction, confidence, float(cov), float(cost))
        for cov in coverages
    }
    default_key = "top_20pct" if "top_20pct" in by_coverage else next(iter(by_coverage), "")
    default_metrics = by_coverage.get(default_key, {})

    payload = {
        "prob_threshold_up": prob_threshold_up,
        "prob_threshold_down": prob_threshold_down,
        "min_edge": min_edge,
        "min_confidence": min_confidence,
        "expected_coverage": default_metrics.get("coverage"),
        "accuracy_at_coverage": default_metrics.get("accuracy_at_coverage"),
        "expectancy_at_coverage": default_metrics.get("expectancy_at_coverage"),
        "drawdown_at_coverage": default_metrics.get("drawdown_at_coverage"),
        "by_coverage": by_coverage,
        "uses_test_for_training": False,
        "fit_scope": "validation_only",
        "message_zh": "阈值优化仅基于验证折结果，必须同时报告覆盖率和样本数。",
    }
    return sanitize_for_json(payload)


def build_calibration_bins(y_true: Iterable[Any], prob: Iterable[Any], bins: int = 10) -> dict[str, Any]:
    y = _as_array(y_true)
    p = _as_array(prob)
    n = min(len(y), len(p))
    y, p = y[:n], p[:n]
    valid = np.isfinite(y) & np.isfinite(p)
    if not valid.any():
        return sanitize_for_json({"bins": [], "ece": None, "brier_score": None, "sample_count": 0})
    y = (y[valid] > 0).astype(float)
    p = np.clip(p[valid], 0.0, 1.0)
    edges = np.linspace(0.0, 1.0, int(bins) + 1)
    rows: list[dict[str, Any]] = []
    ece = 0.0
    for idx in range(int(bins)):
        lower, upper = edges[idx], edges[idx + 1]
        mask = (p >= lower) & (p <= upper if idx == int(bins) - 1 else p < upper)
        count = int(mask.sum())
        if count == 0:
            rows.append({"bin": idx + 1, "lower": float(lower), "upper": float(upper), "sample_count": 0})
            continue
        predicted = float(p[mask].mean())
        realized = float(y[mask].mean())
        contribution = abs(predicted - realized) * (count / len(p))
        ece += contribution
        rows.append(
            {
                "bin": idx + 1,
                "lower": float(lower),
                "upper": float(upper),
                "sample_count": count,
                "predicted_probability_mean": predicted,
                "realized_up_rate": realized,
                "brier_contribution": float(np.mean((p[mask] - y[mask]) ** 2)),
            }
        )
    return sanitize_for_json(
        {
            "bins": rows,
            "ece": float(ece),
            "brier_score": float(np.mean((p - y) ** 2)),
            "sample_count": int(len(p)),
        }
    )
