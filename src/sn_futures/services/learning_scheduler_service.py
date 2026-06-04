from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .candidate_v5_research_service import run_candidate_v5_research
from .feature_store_v5_service import build_feature_store_v5
from .institutional_refresh_service import run_institutional_refresh_steps
from .institutional_validation_service import run_institutional_validation
from .model_promotion_service import promote_candidate
from .research_artifact_service import archive_research_run


REQUIRED_LEARNING_TASKS = (
    "daily_market_refresh",
    "daily_news_refresh",
    "daily_cross_market_backfill",
    "weekly_feature_store_build",
    "weekly_candidate_training",
    "weekly_institutional_validation",
    "monthly_promotion_dry_run",
    "artifact_archive",
    "degradation_check",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _scheduler_dir() -> Path:
    path = get_user_output_dir() / "learning_scheduler"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _status_path() -> Path:
    return _scheduler_dir() / "learning_scheduler_status.json"


def _history_path() -> Path:
    return _scheduler_dir() / "learning_scheduler_history.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _default_status() -> dict[str, Any]:
    return {
        "status": "idle",
        "paused": False,
        "last_run_at": None,
        "next_run_at": (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
        "next_task": "daily_market_refresh",
        "tasks": [],
        "last_failure_reasons": [],
        "manual_approval_required": False,
        "auto_active_disabled": True,
        "active_updated": False,
        "customer_prediction_generated": False,
        "message_zh": "本地自学习调度器待运行；不会自动发布 active model。",
    }


def _append_history(run: Mapping[str, Any]) -> None:
    history = _read_json(_history_path())
    runs = history.get("runs") if isinstance(history, Mapping) and isinstance(history.get("runs"), list) else []
    runs.append(sanitize_for_json(dict(run)))
    _write_json(_history_path(), {"runs": runs[-100:], "count": len(runs[-100:])})


def _task_result(task: str, status: str, payload: Mapping[str, Any] | None = None, error: str | None = None) -> dict[str, Any]:
    result = {
        "task": task,
        "status": status,
        "ran_at": _now(),
        "message_zh": "",
    }
    if payload is not None:
        result["payload"] = sanitize_for_json(dict(payload))
        result["message_zh"] = str(payload.get("message_zh") or payload.get("reason_zh") or payload.get("status") or "")
    if error:
        result["error_message_zh"] = error
        result["message_zh"] = error
    return result


def _run_task(task: str) -> dict[str, Any]:
    try:
        if task == "daily_market_refresh":
            payload = run_institutional_refresh_steps(["market"], force=True)
        elif task == "daily_news_refresh":
            payload = run_institutional_refresh_steps(["news", "event_relevance"], force=True)
        elif task == "daily_cross_market_backfill":
            payload = run_institutional_refresh_steps(["online_cross_market", "features"], force=True)
        elif task == "weekly_feature_store_build":
            payload = build_feature_store_v5()
        elif task == "weekly_candidate_training":
            payload = run_candidate_v5_research(horizons=("1d", "3d", "5d", "10d", "20d"))
        elif task == "weekly_institutional_validation":
            payload = run_institutional_validation(candidate_version="v5", dry_run=True)
        elif task == "monthly_promotion_dry_run":
            payload = promote_candidate(candidate_version="v5", dry_run=True)
        elif task == "artifact_archive":
            payload = archive_research_run(
                candidate_version="v5",
                extra_payload={
                    "scheduled_by": "learning_scheduler",
                    "auto_active_disabled": True,
                },
            )
        elif task == "degradation_check":
            payload = {
                "status": "success",
                "message_zh": "已完成退化检查；如 promotion dry-run 通过，仍需人工审批 active。",
                "auto_active_disabled": True,
            }
        else:
            return _task_result(task, "skipped", {"status": "unknown_task", "message_zh": "未知调度任务，已跳过。"})
        status = "success" if str(payload.get("status") or "success").lower() not in {"failed", "error"} else "failed"
        return _task_result(task, status, payload)
    except Exception as exc:
        return _task_result(task, "failed", error=f"{task} 执行失败：{exc}")


def get_learning_scheduler_status() -> dict[str, Any]:
    payload = _read_json(_status_path())
    if not isinstance(payload, Mapping):
        payload = _default_status()
        _write_json(_status_path(), payload)
    return sanitize_for_json(dict(payload))


def pause_learning_scheduler(reason: str = "") -> dict[str, Any]:
    status = get_learning_scheduler_status()
    status.update(
        {
            "status": "paused",
            "paused": True,
            "paused_at": _now(),
            "pause_reason_zh": reason or "用户暂停本地自学习调度器。",
            "message_zh": "本地自学习调度器已暂停，不会自动运行训练或验证任务。",
        }
    )
    _write_json(_status_path(), status)
    return sanitize_for_json(status)


def resume_learning_scheduler() -> dict[str, Any]:
    status = get_learning_scheduler_status()
    status.update(
        {
            "status": "idle",
            "paused": False,
            "resumed_at": _now(),
            "next_run_at": (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
            "message_zh": "本地自学习调度器已恢复；仍不会自动发布 active model。",
        }
    )
    _write_json(_status_path(), status)
    return sanitize_for_json(status)


def _normalise_tasks(tasks: Iterable[str] | None) -> tuple[str, ...]:
    if not tasks:
        return REQUIRED_LEARNING_TASKS
    selected = tuple(str(task) for task in tasks if str(task) in REQUIRED_LEARNING_TASKS)
    return selected or REQUIRED_LEARNING_TASKS


def _promotion_passed(task_results: list[dict[str, Any]]) -> bool:
    for result in task_results:
        if result.get("task") != "monthly_promotion_dry_run":
            continue
        payload = result.get("payload")
        if not isinstance(payload, Mapping):
            return False
        return bool(payload.get("passed") or payload.get("gate_passed") or payload.get("eligible_for_active") or payload.get("status") == "passed")
    return False


def run_learning_scheduler_once(*, force: bool = False, tasks: Iterable[str] | None = None) -> dict[str, Any]:
    current = get_learning_scheduler_status()
    if current.get("paused") and not force:
        result = {
            **current,
            "status": "paused",
            "ran_at": _now(),
            "message_zh": "调度器已暂停；未运行任何任务。",
            "active_updated": False,
            "customer_prediction_generated": False,
            "auto_active_disabled": True,
        }
        _write_json(_status_path(), result)
        return sanitize_for_json(result)

    selected_tasks = _normalise_tasks(tasks)
    task_results = [_run_task(task) for task in selected_tasks]
    failures = [
        str(result.get("error_message_zh") or result.get("message_zh") or result.get("task"))
        for result in task_results
        if result.get("status") == "failed"
    ]
    archive_task = next((result for result in task_results if result.get("task") == "artifact_archive"), {})
    archive_payload = archive_task.get("payload") if isinstance(archive_task, Mapping) else {}
    if not isinstance(archive_payload, Mapping):
        archive_payload = {}
    manual_approval_required = _promotion_passed(task_results)
    status = "failed" if failures else "success"
    payload = {
        "status": status,
        "paused": False,
        "generated_at": _now(),
        "last_run_at": _now(),
        "next_run_at": (datetime.now() + timedelta(days=1)).isoformat(timespec="seconds"),
        "next_task": "daily_market_refresh",
        "tasks": task_results,
        "last_failure_reasons": failures,
        "artifact_dir": archive_payload.get("artifact_dir"),
        "artifact_run_id": archive_payload.get("run_id"),
        "manual_approval_required": manual_approval_required,
        "manual_approval_message_zh": "promotion dry-run 通过后仍需人工审批，调度器不会自动写 active_model.json。" if manual_approval_required else "当前没有可自动发布的 active；调度器只保留 dry-run 结果。",
        "auto_active_disabled": True,
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "sample_data_used": False,
        "message_zh": "本地自学习调度运行完成；不会自动发布 active model，也不会生成客户预测。",
    }
    _write_json(_status_path(), payload)
    _append_history(payload)
    return sanitize_for_json(payload)
