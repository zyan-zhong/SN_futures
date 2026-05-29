from __future__ import annotations

from datetime import datetime
from typing import Any

from .degradation import evaluate_degradation_gate
from .model_registry import ModelRegistry
from .promotion_gate import evaluate_promotion_gate


def _latest(records, horizon: str, status: str):
    rows = [record for record in records if record.horizon == horizon and record.status == status]
    return sorted(rows, key=lambda item: item.created_at)[-1] if rows else None


def build_learning_status(
    registry: ModelRegistry,
    *,
    task_state: dict[str, Any] | None = None,
    next_task: str = "等待下一次数据刷新或候选训练",
) -> dict[str, Any]:
    task_state = task_state or {}
    records = registry.records()
    active = [record for record in records if record.status in {"active", "paper_active"}]
    candidates = [record for record in records if record.status == "candidate"]
    degraded = [record for record in records if record.status == "degraded"]
    return {
        "updated_at": datetime.now().isoformat(timespec="seconds"),
        "last_market_refresh": task_state.get("last_market_refresh", "暂未运行"),
        "last_prediction": task_state.get("last_prediction", "暂未运行"),
        "last_verification": task_state.get("last_verification", "暂未运行"),
        "last_calibration": task_state.get("last_calibration", "暂未运行"),
        "last_candidate_training": task_state.get("last_candidate_training", "暂未运行"),
        "last_walk_forward": task_state.get("last_walk_forward", "暂未运行"),
        "last_event_ablation": task_state.get("last_event_ablation", "暂未运行"),
        "last_promotion_check": task_state.get("last_promotion_check", "暂未运行"),
        "active_models": [{"horizon": row.horizon, "model_id": row.model_id, "status": row.status} for row in active],
        "candidate_models": [{"horizon": row.horizon, "model_id": row.model_id, "status": row.status} for row in candidates],
        "degraded_models": [{"horizon": row.horizon, "model_id": row.model_id, "failure_reasons": row.failure_reasons} for row in degraded],
        "failure_reasons": [reason for row in records for reason in row.failure_reasons],
        "next_task": next_task,
        "message": "暂无可用 active 模型" if not active else "模型治理状态已更新",
    }


def build_model_health(registry: ModelRegistry, *, horizons: list[str] | None = None) -> dict[str, Any]:
    records = registry.records()
    horizon_names = horizons or sorted({record.horizon for record in records})
    rows: list[dict[str, Any]] = []
    for horizon in horizon_names:
        active = registry.get_active_model(horizon)
        candidate = _latest(records, horizon, "candidate")
        metrics = active.metrics if active is not None else {}
        degradation = evaluate_degradation_gate(metrics).to_dict() if metrics else {
            "degraded": False,
            "reasons": ["暂无可用 active 模型"],
            "metrics_used": {},
        }
        promotion = (
            evaluate_promotion_gate(candidate.metrics, baseline_metrics=metrics).to_dict()
            if candidate is not None and candidate.metrics
            else {"passed": False, "result": "暂无候选模型", "failure_reasons": ["暂未运行 candidate"]}
        )
        rows.append(
            {
                "horizon": horizon,
                "active_model": active.model_id if active is not None else "",
                "candidate_model": candidate.model_id if candidate is not None else "",
                "direction_hit_rate": metrics.get("directional_accuracy"),
                "high_confidence_hit_rate": metrics.get("high_conf_hit_rate"),
                "mae": metrics.get("mae", metrics.get("return_mae")),
                "rmse": metrics.get("rmse", metrics.get("return_rmse")),
                "brier_score": metrics.get("brier_score"),
                "calibration_error": metrics.get("calibration_error"),
                "interval_coverage": metrics.get("interval_coverage"),
                "cost_adjusted_return": metrics.get("net_profit_after_cost"),
                "drawdown": metrics.get("max_drawdown"),
                "promotion_gate_status": promotion,
                "degradation_gate_status": degradation,
            }
        )
    return {"updated_at": datetime.now().isoformat(timespec="seconds"), "horizons": rows}
