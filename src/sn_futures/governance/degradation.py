from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np

from .model_registry import ModelRecord, ModelRegistry


@dataclass(frozen=True)
class DegradationGateConfig:
    max_calibration_error: float = 0.16
    min_data_quality_score: float = 0.90
    emergency_drawdown_threshold: float = 0.25
    min_recent_high_conf_hit_rate: float = 0.50


@dataclass(frozen=True)
class DegradationDecision:
    degraded: bool
    reasons: list[str]
    metrics_used: dict[str, Any]
    config: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "degraded": self.degraded,
            "reasons": self.reasons,
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
        return value.strip().lower() in {"1", "true", "yes", "failed", "fail"}
    if value is None:
        return default
    return bool(value)


def evaluate_degradation_gate(metrics: dict[str, Any], *, config: DegradationGateConfig | None = None) -> DegradationDecision:
    cfg = config or DegradationGateConfig()
    reasons: list[str] = []
    recent_expectancy = _safe_float(metrics.get("recent_30_expectancy", metrics.get("expectancy")))
    recent_hit = _safe_float(metrics.get("recent_60d_high_conf_hit_rate", metrics.get("high_conf_hit_rate")), 1.0)
    calibration_error = _safe_float(metrics.get("calibration_error", metrics.get("expected_calibration_error")))
    data_quality = _safe_float(metrics.get("data_quality_score"), 1.0)
    max_drawdown = abs(_safe_float(metrics.get("max_drawdown")))
    provider_fail = _safe_bool(metrics.get("critical_provider_consecutive_failure"), False)
    wf_failed = _safe_bool(metrics.get("recent_walk_forward_failed"), False)

    if recent_expectancy < 0:
        reasons.append("最近30笔期望收益为负")
    if recent_hit < cfg.min_recent_high_conf_hit_rate:
        reasons.append("最近60天高置信命中率低于阈值")
    if calibration_error > cfg.max_calibration_error:
        reasons.append("概率校准误差超过阈值")
    if data_quality < cfg.min_data_quality_score:
        reasons.append("数据质量不足")
    if max_drawdown > cfg.emergency_drawdown_threshold:
        reasons.append("最大回撤超过紧急阈值")
    if provider_fail:
        reasons.append("关键数据源连续失败")
    if wf_failed:
        reasons.append("最近 walk-forward 验证失败")

    return DegradationDecision(
        degraded=bool(reasons),
        reasons=reasons,
        metrics_used={
            "recent_30_expectancy": recent_expectancy,
            "recent_60d_high_conf_hit_rate": recent_hit,
            "calibration_error": calibration_error,
            "data_quality_score": data_quality,
            "max_drawdown": max_drawdown,
            "critical_provider_consecutive_failure": provider_fail,
            "recent_walk_forward_failed": wf_failed,
        },
        config=asdict(cfg),
    )


def apply_degradation_gate(
    registry: ModelRegistry,
    model_id: str,
    metrics: dict[str, Any],
    *,
    config: DegradationGateConfig | None = None,
) -> DegradationDecision:
    decision = evaluate_degradation_gate(metrics, config=config)
    if decision.degraded:
        registry.degrade_model(model_id, decision.reasons)
    return decision


def guard_degraded_prediction(record: ModelRecord | None, prediction: dict[str, Any]) -> dict[str, Any]:
    guarded = dict(prediction)
    if record is None:
        guarded.update(
            {
                "signal": "观望",
                "direction": "neutral",
                "governance_status": "no_active_model",
                "governance_message": "暂无可用 active 模型",
            }
        )
        for key in ("entry_price", "take_profit", "stop_loss", "price_center", "range_low", "range_high"):
            guarded.pop(key, None)
        return guarded
    if record.status != "degraded":
        guarded.setdefault("governance_status", record.status)
        return guarded
    guarded.update(
        {
            "signal": "观望",
            "direction": "neutral",
            "governance_status": "degraded",
            "governance_message": "模型已降级，仅保留研究观察与风险提示，不输出具体交易点位",
            "failure_reasons": list(record.failure_reasons),
        }
    )
    for key in ("entry_price", "take_profit", "stop_loss", "price_center", "range_low", "range_high"):
        guarded.pop(key, None)
    return guarded
