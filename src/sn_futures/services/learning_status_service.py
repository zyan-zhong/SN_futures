from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from sn_futures.governance import ModelRegistry, build_learning_status

from .payload_utils import sanitize_for_json


def build_api_learning_status(
    *,
    scheduler_state: Mapping[str, Any] | None,
    registry_path: Path | None = None,
    model_health: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    state = dict(scheduler_state or {})
    registry = ModelRegistry(registry_path or Path("app_data/outputs/model_governance_registry.json"))
    task_state = {
        "last_market_refresh": state.get("last_market_refresh", "暂未运行"),
        "last_prediction": state.get("last_prediction_refresh", state.get("last_prediction", "暂未运行")),
        "last_verification": state.get("last_verification", "暂未运行"),
        "last_calibration": state.get("last_calibration", "暂未运行"),
        "last_candidate_training": state.get("last_training", state.get("last_candidate_training", "暂未运行")),
        "last_walk_forward": state.get("last_walk_forward", "暂未运行"),
        "last_event_ablation": state.get("last_event_ablation", "暂未运行"),
        "last_promotion_check": state.get("last_promotion_check", state.get("last_model_governance", "暂未运行")),
    }
    governance = build_learning_status(
        registry,
        task_state=task_state,
        next_task=str(state.get("next_task") or state.get("next_prediction_at") or "等待下一次数据刷新或候选训练"),
    )
    payload = {
        **governance,
        "auto_scheduler_enabled": bool(state.get("auto_scheduler_enabled", True)),
        "last_news_refresh": state.get("last_news_refresh", "暂未运行"),
        "last_prediction_refresh": task_state["last_prediction"],
        "last_training": task_state["last_candidate_training"],
        "next_prediction_at": state.get("next_prediction_at", ""),
        "next_training_at": state.get("next_training_at", ""),
        "is_running": bool(state.get("current_task") or state.get("running_task")),
        "last_failure": state.get("last_error") or state.get("last_task_error") or "",
        "failure_reasons": governance.get("failure_reasons") or ([state.get("last_error")] if state.get("last_error") else []),
        "rate_limit_state": state.get("rate_limit_state", "免费源限频保护：行情高频，新闻/宏观低频，失败保留缓存。"),
        "model_health": dict(model_health or {}),
        "per_horizon": (model_health or {}).get("per_horizon", {}) if isinstance(model_health, Mapping) else {},
        "learning_note": "系统会记录候选训练、滚动验证、校准和晋级检查；未通过 promotion gate 的 candidate 不会覆盖 active。",
    }
    return sanitize_for_json(payload)
