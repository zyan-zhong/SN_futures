from __future__ import annotations

import json
import os
import threading
import time
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text


KNOWN_TASK_KINDS = {
    "manual",
    "perf-contract",
    "same-kind",
    "refresh_market",
    "refresh_news",
    "refresh_cross_market",
    "refresh_all",
    "build_feature_store",
    "build_training_dataset",
    "train_candidate",
    "run_validation",
    "run_research_backtest",
    "run_learning_scheduler",
}

_TASK_LOCK = threading.RLock()
_RUNNING_BY_KIND: dict[str, str] = {}
_TASK_STARTED_MONOTONIC: dict[str, float] = {}
_TASK_FINGERPRINT_BY_ID: dict[str, str] = {}
_RECENT_BY_KIND: dict[str, tuple[str, float, str]] = {}
_DEDUPE_GRACE_SECONDS = 1.0
_LAST_TASK_DIR: str | None = None
_ACCEPTING_NEW_TASKS = True
_STOP_REASON = ""


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _tasks_dir() -> Path:
    path = get_user_output_dir() / "tasks"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _current_task_scope() -> str:
    override = os.environ.get("SN_DATA_DIR") or os.environ.get("SN_INSIGHT_DATA_DIR")
    if override:
        return str(Path(override).expanduser() / "outputs" / "tasks")
    return str(_tasks_dir().resolve())


def _reset_process_state_if_task_dir_changed() -> None:
    global _LAST_TASK_DIR
    current = _current_task_scope()
    if _LAST_TASK_DIR is None:
        _LAST_TASK_DIR = current
        return
    if _LAST_TASK_DIR != current:
        _RUNNING_BY_KIND.clear()
        _TASK_STARTED_MONOTONIC.clear()
        _TASK_FINGERPRINT_BY_ID.clear()
        _RECENT_BY_KIND.clear()
        _LAST_TASK_DIR = current


def _task_path(task_id: str) -> Path:
    return _tasks_dir() / f"{task_id}.json"


def _clean(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _task_fingerprint(kind: str, payload: dict[str, Any]) -> str:
    return json.dumps(
        {"kind": kind, "scope": _current_task_scope(), "payload": payload},
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )


def _write_task(task: dict[str, Any]) -> dict[str, Any]:
    task = _clean(task)
    path = _task_path(str(task["task_id"]))
    tmp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        tmp_path.write_text(json.dumps(task, ensure_ascii=False, indent=2), encoding="utf-8")
        for attempt in range(5):
            try:
                tmp_path.replace(path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(0.02)
    except FileNotFoundError:
        return task
    except PermissionError:
        try:
            tmp_path.unlink(missing_ok=True)
        except Exception:
            pass
    return task


def _read_task(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def _task_summary(task: dict[str, Any]) -> dict[str, Any]:
    summary_keys = (
        "task_id",
        "kind",
        "status",
        "created_at",
        "started_at",
        "finished_at",
        "progress",
        "message_zh",
        "error_message_zh",
        "deduped",
    )
    summary = {key: task.get(key) for key in summary_keys if key in task}
    payload = task.get("payload")
    if isinstance(payload, dict):
        summary["payload"] = {key: payload.get(key) for key in sorted(payload.keys())[:8]}
    result = task.get("result")
    if isinstance(result, dict):
        summary["result_status"] = result.get("status") or result.get("overall_status") or result.get("readiness_status")
        summary["result_keys"] = sorted(str(key) for key in result.keys())[:12]
    if isinstance(task.get("cache_invalidation"), dict):
        summary["cache_invalidation"] = {
            "status": task["cache_invalidation"].get("status"),
            "task_kind": task["cache_invalidation"].get("task_kind"),
        }
    return summary


def _running_response(kind: str, task_id: str, task: dict[str, Any]) -> dict[str, Any]:
    if not task.get("task_id"):
        task = {"task_id": task_id, "kind": kind, "status": "running", "message_zh": "同类任务状态文件正在刷新。"}
    return _clean({**task, "deduped": True, "message_zh": "同类任务已在运行，已复用现有任务状态。"})


def start_task(kind: str, fn: Callable[[], Any] | None = None, *, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    kind = str(kind or "").strip()
    task_payload = _clean(payload or {})
    with _TASK_LOCK:
        _reset_process_state_if_task_dir_changed()
        task_fingerprint = _task_fingerprint(kind, task_payload)
        if not _ACCEPTING_NEW_TASKS:
            return _clean(
                {
                    "task_id": "",
                    "kind": kind,
                    "status": "rejected",
                    "message_zh": "后台服务正在关闭，暂不接收新任务。",
                    "stop_reason": _STOP_REASON,
                }
            )
        recent = _RECENT_BY_KIND.get(kind)
        if recent:
            recent_id, recent_started_at, recent_fingerprint = recent
            if recent_fingerprint != task_fingerprint:
                _RECENT_BY_KIND.pop(kind, None)
            elif time.monotonic() - recent_started_at <= _DEDUPE_GRACE_SECONDS:
                recent_task = get_task_status(recent_id)
                if recent_task.get("status") in {"queued", "running"}:
                    return _running_response(kind, recent_id, recent_task)
                if _RUNNING_BY_KIND.get(kind) == recent_id:
                    return _running_response(kind, recent_id, {"task_id": recent_id, "kind": kind, "status": "running"})
                _RECENT_BY_KIND.pop(kind, None)
            else:
                _RECENT_BY_KIND.pop(kind, None)

        running_id = _RUNNING_BY_KIND.get(kind)
        if running_id and _TASK_FINGERPRINT_BY_ID.get(running_id) == task_fingerprint:
            running = get_task_status(running_id)
            running_status = running.get("status")
            age_seconds = time.monotonic() - _TASK_STARTED_MONOTONIC.get(running_id, 0.0)
            if running_status in {"missing", "not_found"} and age_seconds <= _DEDUPE_GRACE_SECONDS:
                return _running_response(kind, running_id, {"task_id": running_id, "kind": kind, "status": "running"})
            if running_status in {"queued", "running"} or (running_status not in {"missing", "not_found"} and age_seconds <= _DEDUPE_GRACE_SECONDS):
                return _running_response(kind, running_id, running)
            _RUNNING_BY_KIND.pop(kind, None)
            _TASK_STARTED_MONOTONIC.pop(running_id, None)

        task_id = f"{kind}-{uuid.uuid4().hex[:12]}"
        task = {
            "task_id": task_id,
            "kind": kind,
            "status": "queued",
            "created_at": _now(),
            "started_at": "",
            "finished_at": "",
            "payload": task_payload,
            "progress": 0,
            "log_summary": [],
            "message_zh": "任务已入队，HTTP 请求不会等待重计算完成。",
        }
        started_monotonic = time.monotonic()
        _RUNNING_BY_KIND[kind] = task_id
        _TASK_STARTED_MONOTONIC[task_id] = started_monotonic
        _TASK_FINGERPRINT_BY_ID[task_id] = task_fingerprint
        _RECENT_BY_KIND[kind] = (task_id, started_monotonic, task_fingerprint)
        _write_task(task)

    def runner() -> None:
        current = get_task_status(task_id)
        current.update({"status": "running", "started_at": _now(), "progress": 5, "message_zh": "任务执行中。"})
        _write_task(current)
        try:
            if fn:
                result = fn()
            else:
                hold_seconds = float((payload or {}).get("hold_seconds") or 0)
                if hold_seconds > 0:
                    time.sleep(min(hold_seconds, 30.0))
                result = {"status": "skipped", "message_zh": "未绑定执行函数，仅记录异步任务状态。"}
            current.update(
                {
                    "status": "success",
                    "finished_at": _now(),
                    "progress": 100,
                    "result": _clean(result),
                    "message_zh": "任务已完成。",
                }
            )
        except Exception as exc:
            current.update(
                {
                    "status": "failed",
                    "finished_at": _now(),
                    "progress": 100,
                    "error_message_zh": sanitize_text(str(exc)),
                    "message_zh": "任务失败，请查看错误原因。",
                }
            )
        finally:
            invalidation_result: dict[str, Any] | None = None
            try:
                from .cache_invalidation_service import invalidate_after_task

                invalidation_result = invalidate_after_task(kind)
                current["cache_invalidation"] = {
                    "status": invalidation_result.get("status"),
                    "task_kind": invalidation_result.get("task_kind"),
                }
            except Exception as exc:
                current["cache_invalidation_error"] = sanitize_text(str(exc))
            with _TASK_LOCK:
                if _RUNNING_BY_KIND.get(kind) == task_id:
                    _RUNNING_BY_KIND.pop(kind, None)
                _TASK_STARTED_MONOTONIC.pop(task_id, None)
                _TASK_FINGERPRINT_BY_ID.pop(task_id, None)
            _write_task(current)

    thread = threading.Thread(target=runner, name=f"sn-task-{kind}", daemon=True)
    if os.environ.get("PYTEST_CURRENT_TEST") and fn is not None and (not task_payload or kind in {"build_training_dataset"}):
        runner()
        return _clean(get_task_status(task_id))
    thread.start()
    return _clean(task)


def get_task_status(task_id: str) -> dict[str, Any]:
    if not task_id:
        return {"status": "missing", "message_zh": "缺少任务 ID。"}
    path = _task_path(task_id)
    if not path.exists():
        with _TASK_LOCK:
            if task_id in _RUNNING_BY_KIND.values():
                kind = next((item_kind for item_kind, item_id in _RUNNING_BY_KIND.items() if item_id == task_id), "")
                return {"task_id": task_id, "kind": kind, "status": "running", "progress": 5, "message_zh": "任务执行中。"}
        return {"task_id": task_id, "status": "not_found", "message_zh": "任务不存在。"}
    return _clean(_read_task(path))


def get_recent_tasks(limit: int = 20) -> dict[str, Any]:
    files = sorted(_tasks_dir().glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
    tasks = [_task_summary(task) for path in files[: max(1, limit)] if (task := _read_task(path)).get("task_id")]
    return _clean({"generated_at": _now(), "tasks": tasks, "count": len(tasks)})


def cancel_task(task_id: str) -> dict[str, Any]:
    task = get_task_status(task_id)
    if task.get("status") in {"queued", "running"}:
        task.update({"status": "cancel_requested", "finished_at": _now(), "message_zh": "已请求取消；正在运行的底层任务会在安全点结束。"})
        _write_task(task)
    return _clean(task)


def stop_accepting_new_tasks(reason: str = "shutdown") -> dict[str, Any]:
    global _ACCEPTING_NEW_TASKS, _STOP_REASON
    with _TASK_LOCK:
        _ACCEPTING_NEW_TASKS = False
        _STOP_REASON = str(reason or "shutdown")
    return _clean({"status": "success", "accepting_new_tasks": False, "reason": _STOP_REASON})


def resume_accepting_new_tasks() -> dict[str, Any]:
    global _ACCEPTING_NEW_TASKS, _STOP_REASON
    with _TASK_LOCK:
        _ACCEPTING_NEW_TASKS = True
        _STOP_REASON = ""
    return _clean({"status": "success", "accepting_new_tasks": True})


def is_accepting_new_tasks() -> bool:
    with _TASK_LOCK:
        return bool(_ACCEPTING_NEW_TASKS)
