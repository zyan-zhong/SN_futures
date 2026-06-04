from __future__ import annotations

from typing import Any

from ..router_registry import RouterRegistry, RouterRequest
from ...services.task_queue_service import (
    KNOWN_TASK_KINDS,
    cancel_task,
    get_recent_tasks,
    get_task_status,
    start_task,
)


def register_routes(registry: RouterRegistry) -> None:
    registry.route("GET", "/api/terminal/tasks/status", _task_status)
    registry.route("GET", "/api/terminal/tasks/recent", _recent_tasks)
    registry.route("POST", "/api/terminal/tasks/start", _start_task)
    registry.route("POST", "/api/terminal/tasks/cancel", _cancel_task)


def _unknown_task_kind(kind: str) -> tuple[int, dict[str, Any]] | None:
    if kind in KNOWN_TASK_KINDS:
        return None
    return 400, {
        "error": "invalid_task_kind",
        "message": f"Unknown task kind: {kind}",
        "allowed_kinds": sorted(KNOWN_TASK_KINDS),
    }


def _task_status(request: RouterRequest) -> dict[str, Any]:
    return get_task_status(request.query_value("id", ""))


def _recent_tasks(request: RouterRequest) -> dict[str, Any]:
    return get_recent_tasks(int(request.query_value("limit", "20") or "20"))


def _start_task(request: RouterRequest) -> tuple[int, dict[str, Any]] | dict[str, Any]:
    payload = request.json_body()
    kind = str(payload.get("kind") or "manual")
    invalid = _unknown_task_kind(kind)
    if invalid is not None:
        return invalid
    return start_task(kind, payload=payload)


def _cancel_task(request: RouterRequest) -> dict[str, Any]:
    return cancel_task(request.query_value("id", ""))
