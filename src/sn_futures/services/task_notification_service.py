from __future__ import annotations

from datetime import datetime
from typing import Any, Mapping

from ..api.json_utils import sanitize_for_json
from .setup_action_run_ledger_service import summarize_setup_action_telemetry
from .task_queue_service import get_recent_tasks


ACTIVE_STATUSES = {"queued", "running", "cancel_requested"}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _classify_task(kind: Any) -> str:
    task_kind = str(kind or "")
    if task_kind == "train_candidate":
        return "research task"
    if task_kind.startswith("refresh_"):
        return "safe refresh task"
    if task_kind in {"build_feature_store", "build_training_dataset"}:
        return "heavy build task"
    if task_kind in {"run_validation", "run_research_backtest"}:
        return "research validation task"
    return "terminal task"


def _task_summary(task: Mapping[str, Any]) -> dict[str, Any]:
    payload = dict(task)
    payload["classification"] = _classify_task(payload.get("kind"))
    payload["is_prediction_failure"] = False
    payload["customer_prediction_generated"] = False
    return payload


def build_task_notifications(limit: int = 20) -> dict[str, Any]:
    """Read task history and choose a non-stale toast candidate."""

    recent = get_recent_tasks(limit)
    tasks = [_task_summary(task) for task in recent.get("tasks", []) if isinstance(task, Mapping)]
    active_tasks = [task for task in tasks if str(task.get("status")) in ACTIVE_STATUSES]
    failed_tasks = [task for task in tasks if str(task.get("status")) == "failed"]
    toast_task = active_tasks[0] if active_tasks else None
    latest_failed_task = failed_tasks[0] if failed_tasks else None
    stale_failure_suppressed = toast_task is None and latest_failed_task is not None
    setup_action_history = summarize_setup_action_telemetry()

    return sanitize_for_json(
        {
            "status": "ready",
            "generated_at": _now(),
            "notification_version": "1.0",
            "toast_task": toast_task,
            "latest_failed_task": latest_failed_task,
            "stale_failure_suppressed": stale_failure_suppressed,
            "notification_center": {
                "title": "Task Notification Center",
                "tasks": tasks,
                "failed_tasks": failed_tasks,
                "active_tasks": active_tasks,
                "setup_action_history": setup_action_history,
            },
            "setup_action_history": setup_action_history,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )
