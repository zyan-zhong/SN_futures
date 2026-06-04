from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from sn_futures.governance import ModelRegistry, build_model_health

from ..runtime import get_user_output_dir
from .payload_utils import fmt_num, fmt_pct, label, safe_float, sanitize_for_json


def _registry(path: Path | None) -> ModelRegistry:
    return ModelRegistry(path or get_user_output_dir() / "model_governance_registry.json")


def _card_metrics(card: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "active_model": card.get("model_version", ""),
        "candidate_model": card.get("candidate_model_version", ""),
        "direction_hit_rate": card.get("backtest_direction_accuracy", card.get("directional_accuracy")),
        "high_confidence_hit_rate": card.get("strong_signal_accuracy", card.get("high_conf_hit_rate")),
        "mae": card.get("mae"),
        "rmse": card.get("rmse"),
        "brier_score": card.get("brier_score"),
        "calibration_error": card.get("expected_calibration_error", card.get("calibration_error")),
        "interval_coverage": card.get("interval_coverage", card.get("coverage_rate")),
        "cost_adjusted_return": card.get("net_profit_after_cost"),
        "drawdown": card.get("max_drawdown"),
        "promotion_gate_status": {
            "result": card.get("promotion_result", "active_retained_until_candidate_passes_gate"),
            "中文状态": label(card.get("promotion_result", "active_retained_until_candidate_passes_gate")),
            "failure_reasons": [card.get("promotion_failure_reason")] if card.get("promotion_failure_reason") else [],
        },
        "degradation_gate_status": {
            "degraded": card.get("active_or_candidate_status") == "degraded",
            "reasons": card.get("degradation_reasons", []),
        },
        "neutral_rate": card.get("p_neutral", card.get("prob_neutral")),
        "strong_signal_rate": 1.0 if str(card.get("signal_strength", "")).startswith("strong_") else 0.0,
        "failure_reasons": [card.get("promotion_failure_reason")] if card.get("promotion_failure_reason") else [],
    }


def build_api_model_health(
    *,
    cards: Mapping[str, Any],
    registry_path: Path | None = None,
    horizons: list[str] | None = None,
) -> dict[str, Any]:
    registry = _registry(registry_path)
    records = registry.records()
    governance_health = build_model_health(registry, horizons=horizons) if records else {"horizons": []}
    per_horizon: dict[str, Any] = {}

    for row in governance_health.get("horizons", []):
        if isinstance(row, Mapping):
            per_horizon[str(row.get("horizon", ""))] = dict(row)

    for horizon, card in cards.items():
        if isinstance(card, Mapping):
            merged = {**_card_metrics(card), **per_horizon.get(str(horizon), {})}
            merged["promotion_gate_status"] = merged.get("promotion_gate_status") or _card_metrics(card)["promotion_gate_status"]
            merged["degradation_gate_status"] = merged.get("degradation_gate_status") or _card_metrics(card)["degradation_gate_status"]
            merged["中文摘要"] = {
                "现行模型": merged.get("active_model") or "暂无可用 active 模型",
                "候选模型": merged.get("candidate_model") or "暂未运行",
                "方向命中率": fmt_pct(merged.get("direction_hit_rate")),
                "高置信命中率": fmt_pct(merged.get("high_confidence_hit_rate")),
                "概率误差(Brier)": fmt_num(merged.get("brier_score"), 3),
                "校准误差(ECE)": fmt_num(merged.get("calibration_error"), 3),
                "区间覆盖率": fmt_pct(merged.get("interval_coverage")),
                "成本后收益": fmt_pct(merged.get("cost_adjusted_return"), 2),
                "回撤": fmt_pct(merged.get("drawdown"), 2),
            }
            per_horizon[str(horizon)] = sanitize_for_json(merged)

    neutral_values = [
        safe_float(item.get("neutral_rate"))
        for item in per_horizon.values()
        if isinstance(item, Mapping) and safe_float(item.get("neutral_rate")) is not None
    ]
    strong_values = [
        safe_float(item.get("strong_signal_rate"))
        for item in per_horizon.values()
        if isinstance(item, Mapping) and safe_float(item.get("strong_signal_rate")) is not None
    ]
    return sanitize_for_json(
        {
            "validation_mode": "walk_forward_or_live_cache",
            "effective_sample_count": 0,
            "neutral_rate": sum(neutral_values) / len(neutral_values) if neutral_values else None,
            "strong_signal_rate": sum(strong_values) / len(strong_values) if strong_values else None,
            "per_horizon": per_horizon,
            "metric_labels": {
                "direction_hit_rate": "方向命中率",
                "high_confidence_hit_rate": "高置信信号命中率",
                "mae": "平均绝对误差(MAE)",
                "rmse": "均方根误差(RMSE)",
                "brier_score": "概率误差(Brier)",
                "calibration_error": "校准误差(ECE)",
                "interval_coverage": "区间覆盖率",
                "cost_adjusted_return": "成本后收益",
                "drawdown": "回撤",
            },
            "health_reason": "仅展示真实缓存、walk-forward 或已兑现结果；候选模型未通过 promotion gate 时不会替换 active。",
        }
    )
