from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np


@dataclass(frozen=True)
class PromotionGateConfig:
    min_oos_sharpe: float = 0.8
    max_drawdown_threshold: float = 0.18
    min_trade_count: int = 80
    min_high_conf_hit_rate_lift: float = 0.05
    min_profit_factor: float = 1.1
    cost_buffer_multiple: float = 2.0
    min_data_quality_score: float = 0.90
    max_calibration_error: float = 0.12


@dataclass(frozen=True)
class PromotionDecision:
    passed: bool
    result: str
    failure_reasons: list[str]
    metrics_used: dict[str, Any]
    config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "passed": self.passed,
            "result": self.result,
            "failure_reasons": self.failure_reasons,
            "metrics_used": self.metrics_used,
            "config": self.config,
        }


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "pass", "passed", "ok"}
    if value is None:
        return default
    return bool(value)


def extract_governance_metrics(result: dict[str, Any]) -> dict[str, Any]:
    """Extract gate metrics from real backtest/walk-forward result dictionaries."""

    metrics = {}
    if isinstance(result.get("metrics"), dict):
        metrics.update(result["metrics"])
    if isinstance(result.get("oos_metrics"), dict):
        metrics.update(result["oos_metrics"])
    if isinstance(result.get("walk_forward"), dict) and isinstance(result["walk_forward"].get("metrics"), dict):
        metrics.update(result["walk_forward"]["metrics"])
    if isinstance(result.get("backtest"), dict) and isinstance(result["backtest"].get("metrics"), dict):
        metrics.update(result["backtest"]["metrics"])
    metrics.update({key: value for key, value in result.items() if key not in {"metrics", "oos_metrics", "walk_forward", "backtest"}})
    return metrics


def evaluate_promotion_gate(
    backtest_result: dict[str, Any],
    *,
    baseline_metrics: dict[str, Any] | None = None,
    assumed_cost: float = 0.0,
    config: PromotionGateConfig | None = None,
) -> PromotionDecision:
    cfg = config or PromotionGateConfig()
    baseline_metrics = baseline_metrics or {}
    metrics = extract_governance_metrics(backtest_result)
    baseline_hit_rate = _safe_float(baseline_metrics.get("high_conf_hit_rate"), 0.0)
    failure: list[str] = []

    oos_sharpe = _safe_float(metrics.get("oos_sharpe", metrics.get("sharpe")))
    net_profit = _safe_float(metrics.get("net_profit_after_cost"))
    max_drawdown = abs(_safe_float(metrics.get("max_drawdown")))
    trade_count = int(_safe_float(metrics.get("trade_count")))
    high_conf_hit_rate = _safe_float(metrics.get("high_conf_hit_rate"))
    profit_factor = _safe_float(metrics.get("profit_factor"))
    break_even_cost = _safe_float(metrics.get("break_even_cost"))
    recent_ok = _safe_bool(metrics.get("recent_window_not_degraded"), False)
    data_quality = _safe_float(metrics.get("data_quality_score"))
    calibration_error = _safe_float(metrics.get("calibration_error", metrics.get("expected_calibration_error")))
    no_leakage = _safe_bool(metrics.get("no_leakage_check_passed"), False)

    if oos_sharpe <= cfg.min_oos_sharpe:
        failure.append("样本外夏普低于阈值")
    if net_profit <= 0:
        failure.append("成本后收益为负")
    if max_drawdown >= cfg.max_drawdown_threshold:
        failure.append("最大回撤超过阈值")
    if trade_count < cfg.min_trade_count:
        failure.append("交易次数不足")
    if high_conf_hit_rate <= baseline_hit_rate + cfg.min_high_conf_hit_rate_lift:
        failure.append("高置信命中率未显著超过基准")
    if profit_factor <= cfg.min_profit_factor:
        failure.append("盈利因子低于阈值")
    if break_even_cost <= cfg.cost_buffer_multiple * abs(float(assumed_cost)):
        failure.append("成本安全垫不足")
    if not recent_ok:
        failure.append("最近窗口表现退化")
    if data_quality < cfg.min_data_quality_score:
        failure.append("数据质量不足")
    if calibration_error > cfg.max_calibration_error:
        failure.append("概率校准误差过高")
    if not no_leakage:
        failure.append("未来函数检查未通过")

    passed = not failure
    return PromotionDecision(
        passed=passed,
        result="candidate_promoted" if passed else "candidate_failed_active_retained",
        failure_reasons=failure,
        metrics_used={
            "oos_sharpe": oos_sharpe,
            "net_profit_after_cost": net_profit,
            "max_drawdown": max_drawdown,
            "trade_count": trade_count,
            "high_conf_hit_rate": high_conf_hit_rate,
            "baseline_high_conf_hit_rate": baseline_hit_rate,
            "profit_factor": profit_factor,
            "break_even_cost": break_even_cost,
            "assumed_cost": assumed_cost,
            "recent_window_not_degraded": recent_ok,
            "data_quality_score": data_quality,
            "calibration_error": calibration_error,
            "no_leakage_check_passed": no_leakage,
        },
        config=asdict(cfg),
    )
