from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


V7_ALLOWED_MODELS = (
    "hist_gradient_boosting",
    "extra_trees",
    "random_forest",
    "compact_lightgbm_if_available",
    "huber_return",
    "elasticnet_return",
)
V8_STABLE_MODELS = (
    "hist_gradient_boosting",
    "random_forest",
    "huber_return",
    "elasticnet_return",
)
DEFAULT_NO_TRADE_FILTERS = (
    "low_confidence",
    "low_edge",
    "high_volatility",
    "high_cost_pressure",
    "stale_data",
    "low_liquidity",
    "sparse_holding_missing",
    "roll_period",
    "drawdown_guard",
    "regime_guard",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _out() -> Path:
    return get_user_output_dir()


def _policy_path(target_candidate_version: str) -> Path:
    version = str(target_candidate_version or "v8").strip().lower() or "v8"
    return _out() / "model_research" / f"candidate_{version}" / f"stable_strategy_policy_{version}.json"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


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


def _days(horizon: str) -> int:
    try:
        return max(1, int(str(horizon).lower().replace("d", "")))
    except Exception:
        return 1


def _validation_metrics(validation: Mapping[str, Any]) -> dict[str, float]:
    return {
        "PBO": _safe_float(_nested(validation, "probability_of_backtest_overfitting", "pbo"), _safe_float(validation.get("pbo"), 0.0)),
        "DSR": _safe_float(_nested(validation, "deflated_sharpe_ratio", "deflated_sharpe_ratio"), _safe_float(validation.get("dsr"), 0.0)),
        "Reality Check p-value": _safe_float(_nested(validation, "reality_check", "p_value"), _safe_float(validation.get("reality_check_p_value"), 1.0)),
    }


def _stable_features(stability: Mapping[str, Any]) -> tuple[list[str], list[str]]:
    stable = [str(item) for item in stability.get("stable_features") or [] if str(item)]
    unstable = [str(item) for item in stability.get("unstable_features") or [] if str(item)]
    selected = [item for item in stable if item not in set(unstable)]
    return selected, unstable


def _horizon_policy(horizon: str, metrics: Mapping[str, Any], *, high_pbo: bool) -> dict[str, Any]:
    naive = _safe_float(metrics.get("naive_directional_accuracy"), 0.50)
    accuracy = _safe_float(metrics.get("directional_accuracy"), _safe_float(metrics.get("accuracy"), 0.0))
    brier = _safe_float(metrics.get("brier_score"), 0.25)
    expectancy = _safe_float(metrics.get("cost_adjusted_expectancy"), _safe_float(metrics.get("expectancy"), 0.0))
    drawdown = abs(_safe_float(metrics.get("max_drawdown_proxy"), _safe_float(metrics.get("max_drawdown"), 0.0)))
    turnover = _safe_float(metrics.get("turnover"), 0.0)
    atr_p95 = _safe_float(metrics.get("atr_percentile_p95"), 0.0)
    roll_exposure = _safe_float(metrics.get("roll_period_exposure"), 0.0)
    stale_rate = _safe_float(metrics.get("stale_data_rate"), 0.0)
    cost_pressure = _safe_float(metrics.get("cost_pressure_p95"), 0.0)

    reasons: list[str] = []
    action = "selective_trade"
    trade_enabled = True
    weak_direction = accuracy <= naive + 0.02 or brier > 0.24 or expectancy < 0.0
    if _days(horizon) <= 1 and weak_direction:
        action = "research_only"
        trade_enabled = False
        reasons.append("weak_direction_or_brier")

    drawdown_guard = drawdown > 0.25
    if drawdown_guard:
        reasons.append("drawdown_proxy_high")
    if atr_p95 >= 0.90:
        reasons.append("high_volatility")
    if roll_exposure >= 0.10:
        reasons.append("roll_period_exposure")
    if stale_rate >= 0.05:
        reasons.append("stale_data_exposure")
    if cost_pressure >= 0.75:
        reasons.append("high_cost_pressure")

    min_confidence = 0.58
    min_trade_edge = 0.0003
    max_trade_rate = 0.18
    if high_pbo:
        min_confidence = max(min_confidence, 0.62)
        max_trade_rate = min(max_trade_rate, 0.15)
    if drawdown_guard:
        min_confidence = max(min_confidence, 0.68)
        min_trade_edge = max(min_trade_edge, 0.0007)
        max_trade_rate = min(max_trade_rate, 0.12)
    if turnover > 0.50:
        max_trade_rate = min(max_trade_rate, 0.10)
    if cost_pressure >= 0.75:
        min_trade_edge = max(min_trade_edge, 0.0008)

    return {
        "horizon": str(horizon),
        "trade_enabled": bool(trade_enabled),
        "action": action,
        "reasons": sorted(set(reasons)),
        "drawdown_guard": bool(drawdown_guard),
        "volatility_guard": bool(atr_p95 >= 0.90),
        "regime_guard": bool(drawdown_guard or high_pbo),
        "min_confidence": round(float(min_confidence), 4),
        "min_trade_edge": round(float(min_trade_edge), 6),
        "max_trade_rate": round(float(max_trade_rate), 4),
        "input_metrics": {
            "directional_accuracy": accuracy,
            "naive_directional_accuracy": naive,
            "brier_score": brier,
            "cost_adjusted_expectancy": expectancy,
            "max_drawdown_proxy_abs": drawdown,
            "turnover": turnover,
        },
    }


def build_stable_strategy_policy(
    *,
    source_candidate_version: str = "v7",
    target_candidate_version: str = "v8",
    horizon_metrics: Mapping[str, Mapping[str, Any]] | None = None,
    institutional_validation: Mapping[str, Any] | None = None,
    research_backtest: Mapping[str, Any] | None = None,
    feature_stability: Mapping[str, Any] | None = None,
    v7_models: tuple[str, ...] | list[str] | None = None,
    write: bool = False,
) -> dict[str, Any]:
    validation = institutional_validation or {}
    stability = feature_stability or {}
    metrics_by_horizon = {str(key): dict(value) for key, value in (horizon_metrics or {}).items() if isinstance(value, Mapping)}
    if not metrics_by_horizon and isinstance((research_backtest or {}).get("horizons"), Mapping):
        for horizon, payload in ((research_backtest or {}).get("horizons") or {}).items():
            if isinstance(payload, Mapping) and isinstance(payload.get("metrics"), Mapping):
                metrics_by_horizon[str(horizon)] = dict(payload["metrics"])

    validation_summary = _validation_metrics(validation)
    high_pbo = validation_summary["PBO"] > 0.5
    horizon_policy = {
        horizon: _horizon_policy(horizon, metrics, high_pbo=high_pbo)
        for horizon, metrics in sorted(metrics_by_horizon.items(), key=lambda item: _days(item[0]))
    }
    selected, unstable = _stable_features(stability)
    allowed = tuple(str(item) for item in (v7_models or V7_ALLOWED_MODELS))
    models = tuple(item for item in V8_STABLE_MODELS if item in set(allowed))
    if not models:
        models = ("hist_gradient_boosting", "random_forest")

    actions: set[str] = {"reduce_trade_frequency", "feature_stability_selection"}
    if high_pbo:
        actions.add("reduce_model_complexity")
    if validation_summary["DSR"] <= 0.0:
        actions.add("require_positive_dsr_before_approval")
    if validation_summary["Reality Check p-value"] >= 0.50:
        actions.add("reality_check_blocker_remains")
    if any(item.get("drawdown_guard") for item in horizon_policy.values()):
        actions.add("drawdown_guard")

    min_confidence = max([_safe_float(item.get("min_confidence"), 0.58) for item in horizon_policy.values()] or [0.62])
    min_trade_edge = max([_safe_float(item.get("min_trade_edge"), 0.0003) for item in horizon_policy.values()] or [0.0003])
    max_trade_rate = min([_safe_float(item.get("max_trade_rate"), 0.15) for item in horizon_policy.values()] or [0.15])
    payload = {
        "status": "success",
        "generated_at": _now(),
        "source_candidate_version": str(source_candidate_version),
        "candidate_version": str(target_candidate_version),
        "target_candidate_version": str(target_candidate_version),
        "policy_path": str(_policy_path(target_candidate_version)),
        "horizon_policy": horizon_policy,
        "disabled_horizons": [key for key, item in horizon_policy.items() if not bool(item.get("trade_enabled"))],
        "no_trade_reasons": sorted({reason for item in horizon_policy.values() for reason in (item.get("reasons") or [])}),
        "no_trade_filters": list(DEFAULT_NO_TRADE_FILTERS),
        "threshold_policy": {
            "coverage_targets": ["top10", "top15"],
            "min_confidence": round(float(min_confidence), 4),
            "min_trade_edge": round(float(min_trade_edge), 6),
            "max_trade_rate": round(float(max_trade_rate), 4),
        },
        "feature_selection": {
            "policy": "drop_fold_unstable_features",
            "stable_features": selected,
            "dropped_unstable_features": unstable,
            "selected_features": selected,
        },
        "complexity": {
            "source_models": list(allowed),
            "models": list(models),
            "not_higher_than_v7": bool(set(models).issubset(set(allowed)) and len(models) <= len(allowed)),
            "removed_for_stability": [item for item in allowed if item not in set(models)],
        },
        "training_fold_only_selection": True,
        "validation_fold_tuning": False,
        "uses_final_backtest_for_tuning": False,
        "validation_summary": validation_summary,
        "actions": sorted(actions),
        "active_updated": False,
        "customer_prediction_generated": False,
        "promotion_gate_lowered": False,
        "message": "Stable candidate policy built from v7 evidence without lowering gates or adding model complexity.",
    }
    if write:
        _write_json(_policy_path(target_candidate_version), payload)
    return sanitize_for_json(payload)
