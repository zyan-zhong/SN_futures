from __future__ import annotations

from typing import Any, Mapping

from .payload_utils import fmt_num, fmt_pct, sanitize_for_json


def _selected_metrics(health: Mapping[str, Any], horizon: str) -> dict[str, Any]:
    per = health.get("per_horizon", {}) if isinstance(health.get("per_horizon"), Mapping) else {}
    item = per.get(horizon) if horizon else None
    return dict(item) if isinstance(item, Mapping) else {}


def build_backtest_diagnostics(
    *,
    horizon: str,
    health: Mapping[str, Any],
    promotion_report: Mapping[str, Any],
    latest_asof_date: str = "",
    latest_row_status: str = "",
) -> dict[str, Any]:
    selected = _selected_metrics(health, horizon)
    failure_reasons = []
    for key in ("failure_reasons", "missing_metrics"):
        value = promotion_report.get(key)
        if isinstance(value, list):
            failure_reasons.extend(str(item) for item in value if item)
    if promotion_report.get("promotion_reason"):
        failure_reasons.append(str(promotion_report["promotion_reason"]))
    if not failure_reasons:
        failure_reasons.append("暂无失败原因；若未运行 walk-forward，则不生成伪造指标。")

    cost_sensitivity = {
        "0.5x成本": selected.get("cost_sensitivity_0_5x", "本周期未更新"),
        "1x成本": selected.get("cost_adjusted_return", "本周期未更新"),
        "2x成本": selected.get("cost_sensitivity_2x", "本周期未更新"),
        "3x成本": selected.get("cost_sensitivity_3x", "本周期未更新"),
    }
    return sanitize_for_json(
        {
            "horizon": horizon or "all",
            "latest_asof_date": latest_asof_date,
            "latest_row_status": latest_row_status,
            "walk_forward_metrics": {
                "方向命中率": fmt_pct(selected.get("direction_hit_rate")),
                "高置信命中率": fmt_pct(selected.get("high_confidence_hit_rate")),
                "MAE": fmt_num(selected.get("mae"), 2),
                "RMSE": fmt_num(selected.get("rmse"), 2),
                "概率误差(Brier)": fmt_num(selected.get("brier_score"), 3),
                "校准误差(ECE)": fmt_num(selected.get("calibration_error"), 3),
                "区间覆盖率": fmt_pct(selected.get("interval_coverage")),
                "成本后收益": fmt_pct(selected.get("cost_adjusted_return"), 2),
                "回撤": fmt_pct(selected.get("drawdown"), 2),
            },
            "selected_horizon_metrics": selected,
            "baseline_comparison": promotion_report.get("baseline", {}),
            "cost_sensitivity": cost_sensitivity,
            "by_regime_performance": selected.get("by_regime_performance", {}),
            "by_signal_strength_performance": selected.get("by_signal_strength_performance", {}),
            "promotion_result": promotion_report.get("promotion_result", "active_retained"),
            "promotion_gate_conclusion": promotion_report.get("promotion_reason", "候选模型未通过完整门槛前保留 active。"),
            "failure_reasons": failure_reasons,
            "walk_forward_status": "cached_or_pending",
            "message": "仅展示真实 walk-forward/兑现诊断；指标缺失时显示样本不足，不填充伪指标。",
        }
    )
