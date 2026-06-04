from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

import numpy as np

from ..api.json_utils import sanitize_for_json


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _nested(mapping: Mapping[str, Any], *keys: str) -> Any:
    current: Any = mapping
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _cost_expectancies(research_backtest: Mapping[str, Any]) -> tuple[float, float]:
    horizons = research_backtest.get("horizons") if isinstance(research_backtest.get("horizons"), Mapping) else {}
    two_x: list[float] = []
    three_x: list[float] = []
    for payload in horizons.values():
        metrics = payload.get("metrics") if isinstance(payload, Mapping) and isinstance(payload.get("metrics"), Mapping) else {}
        stress = metrics.get("cost_stress") if isinstance(metrics.get("cost_stress"), Mapping) else {}
        two_x.append(_safe_float(_nested(stress, "2x_cost", "expectancy"), 0.0))
        three_x.append(_safe_float(_nested(stress, "3x_cost", "expectancy"), 0.0))
    return (
        float(sum(two_x) / max(len(two_x), 1)),
        float(sum(three_x) / max(len(three_x), 1)),
    )


def _average_turnover(research_backtest: Mapping[str, Any]) -> float:
    horizons = research_backtest.get("horizons") if isinstance(research_backtest.get("horizons"), Mapping) else {}
    values: list[float] = []
    for payload in horizons.values():
        metrics = payload.get("metrics") if isinstance(payload, Mapping) and isinstance(payload.get("metrics"), Mapping) else {}
        values.append(_safe_float(metrics.get("turnover"), 0.0))
    return float(sum(values) / max(len(values), 1))


def optimize_stability_objective(
    *,
    candidate_version: str,
    institutional_validation: Mapping[str, Any] | None = None,
    research_backtest: Mapping[str, Any] | None = None,
    feature_stability: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Summarize stability pressure and recommend conservative v7 thresholds.

    This does not tune on final backtest output. It records how the next
    candidate configuration should become more conservative when PBO/cost
    stress/feature instability are poor.
    """

    validation = institutional_validation or {}
    backtest = research_backtest or {}
    stability = feature_stability or {}
    pbo = _safe_float(_nested(validation, "probability_of_backtest_overfitting", "pbo"), _safe_float(validation.get("pbo"), 0.0))
    dsr = _safe_float(_nested(validation, "deflated_sharpe_ratio", "deflated_sharpe_ratio"), _safe_float(validation.get("dsr"), 0.0))
    reality_p = _safe_float(_nested(validation, "reality_check", "p_value"), _safe_float(validation.get("reality_check_p_value"), 1.0))
    two_x, three_x = _cost_expectancies(backtest)
    turnover = _average_turnover(backtest)
    stability_score = _safe_float(stability.get("stability_score"), 0.0)

    actions: list[str] = []
    min_confidence = 0.56
    min_trade_edge = 0.0002
    max_trade_rate = 0.30
    complexity = "standard_tree_ensemble"

    if pbo > 0.5:
        actions.extend(["reduce_model_complexity", "reduce_trade_frequency"])
        min_confidence = max(min_confidence, 0.62)
        max_trade_rate = min(max_trade_rate, 0.18)
        complexity = "conservative_tree_ensemble"
    if two_x < 0.0 or three_x < 0.0:
        actions.extend(["increase_min_trade_edge", "increase_min_confidence", "high_cost_pressure_filter"])
        min_trade_edge = max(min_trade_edge, abs(min(two_x, three_x)) + 0.0002)
        min_confidence = max(min_confidence, 0.60)
    if dsr <= 0.0:
        actions.append("require_positive_dsr_before_approval")
    if turnover > 0.5:
        actions.append("turnover_cap")
        max_trade_rate = min(max_trade_rate, 0.15)
    if stability_score < 0.55:
        actions.append("drop_unstable_features_or_lower_weight")

    promotion_recommended = bool(pbo <= 0.2 and dsr > 0 and reality_p < 0.05 and two_x > 0 and three_x > 0 and stability_score >= 0.55)
    payload = {
        "candidate_version": candidate_version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "objective": {
            "maximize": ["cost_adjusted_expectancy", "top20_accuracy", "feature_stability", "DSR"],
            "minimize": ["PBO", "max_drawdown", "turnover", "fold_concentration", "year_concentration", "regime_concentration"],
        },
        "metrics": {
            "PBO": pbo,
            "DSR": dsr,
            "Reality Check p-value": reality_p,
            "2x cost expectancy": two_x,
            "3x cost expectancy": three_x,
            "cost_stress": {"2x_cost_expectancy": two_x, "3x_cost_expectancy": three_x},
            "turnover": turnover,
            "feature_stability": stability_score,
        },
        "recommended_min_confidence": min_confidence,
        "recommended_min_trade_edge": min_trade_edge,
        "recommended_max_trade_rate": max_trade_rate,
        "recommended_complexity": complexity,
        "actions": sorted(set(actions)),
        "promotion_recommended": promotion_recommended,
        "rules": [
            "thresholds_selected_on_training_folds_only",
            "validation_folds_evaluation_only",
            "no_final_backtest_reverse_tuning",
            "high_pbo_reduces_complexity_and_trade_frequency",
            "negative_cost_stress_raises_edge_and_confidence",
        ],
    }
    return sanitize_for_json(payload)
