from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Mapping
from uuid import uuid4

from ..api.json_utils import sanitize_for_json
from ..utils.secret_sanitizer import sanitize_mapping
from .provider_closed_loop_service import build_provider_closed_loop_refresh_status
from .provider_smoke_result_bridge_service import DOWNSTREAM_FLAGS, get_public_provider_smoke_report
from .runtime import data_watermark_path, public_terminal_dir


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe(payload: Any) -> Any:
    return sanitize_for_json(sanitize_mapping(payload))


def _task_dir():
    path = public_terminal_dir() / "tasks"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _task_path(task_id: str):
    safe_id = "".join(ch for ch in str(task_id) if ch.isalnum() or ch in {"-", "_"})[:80]
    return _task_dir() / f"{safe_id}.json"


def _result_to_task(task_id: str, result: Mapping[str, Any]) -> dict[str, Any]:
    return _safe(
        {
            "task_id": task_id,
            "status": str(result.get("status") or "blocked"),
            "progress": 1.0,
            "reason": str(result.get("reason") or ""),
            "result": result.get("result") if isinstance(result.get("result"), Mapping) else {},
            "provider_coverage": list(result.get("provider_coverage") or []),
            "missing_data": list(result.get("missing_data") or []),
            **{flag: False for flag in DOWNSTREAM_FLAGS},
        }
    )


def _write_task(task: Mapping[str, Any]) -> dict[str, Any]:
    task_id = str(task.get("task_id") or "")
    path = _task_path(task_id)
    payload = _safe(task)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return dict(payload)


def run_public_refresh_data_status() -> dict[str, Any]:
    report = get_public_provider_smoke_report()
    closed_loop = build_provider_closed_loop_refresh_status(report)
    if closed_loop.get("status") != "success":
        return _safe(
            {
                "status": "blocked",
                "reason": str(closed_loop.get("reason") or "no_active_provider_smoke_pass"),
                "provider_coverage": list(closed_loop.get("provider_coverage") or []),
                "missing_data": list(closed_loop.get("missing_data") or ["provider_closed_loop_ready_record"]),
                **{flag: False for flag in DOWNSTREAM_FLAGS},
            }
        )

    total_rows = int(closed_loop.get("row_count") or 0)
    watermark = _safe(
        {
            **dict(closed_loop.get("data_watermark") if isinstance(closed_loop.get("data_watermark"), Mapping) else {}),
            "reason": "",
            "generated_at": _now(),
            "provider_smoke_report_path": report.get("report_path", ""),
            "provider_coverage": list(closed_loop.get("provider_coverage") or []),
            "row_count": total_rows,
            "sample_data_used": False,
            "baseline_used": False,
            **{flag: False for flag in DOWNSTREAM_FLAGS},
        }
    )
    path = data_watermark_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(watermark, ensure_ascii=False, indent=2), encoding="utf-8")
    return _safe(
        {
            "status": "success",
            "result": {
                "data_watermark_updated": True,
                "data_watermark_path": str(path),
                "provider_coverage": watermark["provider_coverage"],
                "row_count": total_rows,
            },
            "provider_coverage": watermark["provider_coverage"],
            "missing_data": [],
            **{flag: False for flag in DOWNSTREAM_FLAGS},
        }
    )


def start_public_refresh_data_status_task() -> dict[str, Any]:
    task_id = f"public-refresh-{uuid4().hex[:12]}"
    started = _safe(
        {
            "task_id": task_id,
            "status": "running",
            "progress": 0.25,
            "reason": "",
            "result": {},
            "provider_coverage": [],
            "missing_data": [],
            **{flag: False for flag in DOWNSTREAM_FLAGS},
        }
    )
    result = run_public_refresh_data_status()
    _write_task(_result_to_task(task_id, result))
    return started


def get_public_refresh_task(task_id: str) -> dict[str, Any]:
    path = _task_path(task_id)
    if not path.exists():
        return _safe(
            {
                "task_id": task_id,
                "status": "blocked",
                "progress": 0.0,
                "reason": "task_not_found",
                "result": {},
                "provider_coverage": [],
                "missing_data": ["task_not_found"],
                **{flag: False for flag in DOWNSTREAM_FLAGS},
            }
        )
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
    return _safe(payload if isinstance(payload, Mapping) else {})


def cancel_public_refresh_task(task_id: str) -> dict[str, Any]:
    current = get_public_refresh_task(task_id)
    status = current.get("status")
    cancelled = {
        **current,
        "task_id": task_id,
        "cancel_requested": True,
        "status": "cancel_requested" if status in {"queued", "running"} else status or "blocked",
        **{flag: False for flag in DOWNSTREAM_FLAGS},
    }
    return _write_task(cancelled)
