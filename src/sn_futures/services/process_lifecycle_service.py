from __future__ import annotations

import json
import os
import socket
import uuid
import ctypes
from datetime import datetime
from pathlib import Path
from typing import Any

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_data_dir
from ..utils.secret_sanitizer import sanitize_mapping


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def runtime_dir() -> Path:
    path = get_user_data_dir() / "runtime"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _pid_path() -> Path:
    return runtime_dir() / "server.pid"


def _port_path() -> Path:
    return runtime_dir() / "server_port.json"


def _session_path() -> Path:
    return runtime_dir() / "server_session.json"


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _is_pid_running(pid: int | None) -> bool:
    if not pid or pid <= 0:
        return False
    if os.name == "nt":
        try:
            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
            process_query_limited_information = 0x1000
            handle = kernel32.OpenProcess(process_query_limited_information, False, int(pid))
            if not handle:
                return False
            try:
                exit_code = ctypes.c_ulong()
                if not kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return False
                still_active = 259
                return int(exit_code.value) == still_active
            finally:
                kernel32.CloseHandle(handle)
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False
    except Exception:
        return False


def write_server_runtime_files(host: str, port: int, session_id: str | None = None) -> dict[str, Any]:
    session_id = session_id or uuid.uuid4().hex
    payload = {
        "pid": os.getpid(),
        "host": str(host or "127.0.0.1"),
        "port": int(port),
        "session_id": session_id,
        "started_at": _now(),
        "hostname": socket.gethostname(),
        "shutdown_requested": False,
    }
    runtime_dir().mkdir(parents=True, exist_ok=True)
    _pid_path().write_text(str(payload["pid"]), encoding="utf-8")
    _port_path().write_text(json.dumps({"host": payload["host"], "port": payload["port"]}, ensure_ascii=False, indent=2), encoding="utf-8")
    _session_path().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    result = {
        **payload,
        "pid_file": str(_pid_path()),
        "pid_file_exists": _pid_path().exists(),
        "runtime_dir": str(runtime_dir()),
    }
    return sanitize_for_json(sanitize_mapping(result))


def get_process_status() -> dict[str, Any]:
    session = _read_json(_session_path())
    port_payload = _read_json(_port_path())
    pid_file_exists = _pid_path().exists()
    pid: int | None = None
    if pid_file_exists:
        try:
            pid = int(_pid_path().read_text(encoding="utf-8").strip())
        except Exception:
            pid = None
    if pid is None and isinstance(session.get("pid"), int):
        pid = int(session["pid"])
    port = port_payload.get("port", session.get("port"))
    status = {
        "generated_at": _now(),
        "pid": pid,
        "port": port,
        "host": port_payload.get("host", session.get("host", "127.0.0.1")),
        "session_id": session.get("session_id", ""),
        "started_at": session.get("started_at", ""),
        "shutdown_requested": bool(session.get("shutdown_requested")),
        "shutdown_at": session.get("shutdown_at", ""),
        "pid_file_exists": pid_file_exists,
        "pid_running": _is_pid_running(pid),
        "stale": not pid_file_exists,
        "runtime_dir": str(runtime_dir()),
        "message_zh": "后台服务运行状态已读取；该接口不会执行慢 provider 检查。",
    }
    return sanitize_for_json(sanitize_mapping(status))


def mark_server_shutdown(reason: str = "") -> dict[str, Any]:
    session = _read_json(_session_path())
    session.update(
        {
            "shutdown_requested": True,
            "shutdown_at": _now(),
            "shutdown_reason": str(reason or "manual"),
            "pid_file_removed": True,
        }
    )
    runtime_dir().mkdir(parents=True, exist_ok=True)
    _session_path().write_text(json.dumps(sanitize_mapping(session), ensure_ascii=False, indent=2), encoding="utf-8")
    try:
        _pid_path().unlink(missing_ok=True)
    except Exception:
        pass
    return sanitize_for_json(
        {
            "status": "shutdown_marked",
            "shutdown_at": session["shutdown_at"],
            "reason": str(reason or "manual"),
            "pid_file_exists": _pid_path().exists(),
            "message_zh": "后台服务已标记为关闭；HTTP server 将由运行时优雅退出。",
        }
    )


def request_server_shutdown(reason: str = "api") -> dict[str, Any]:
    task_queue_status: dict[str, Any] = {"accepting_new_tasks": False}
    try:
        from .task_queue_service import stop_accepting_new_tasks

        task_queue_status = stop_accepting_new_tasks(reason=reason)
    except Exception:
        pass
    shutdown = mark_server_shutdown(reason=reason)
    return sanitize_for_json(
        sanitize_mapping(
            {
                **shutdown,
                "status": "shutdown_requested",
                "accepting_new_tasks": bool(task_queue_status.get("accepting_new_tasks", False)),
                "task_queue_status": task_queue_status.get("status", "unknown"),
                "http_shutdown_scheduled": True,
                "active_updated": False,
                "customer_prediction_generated": False,
                "baseline_used": False,
                "fake_prediction_generated": False,
                "message_zh": "后台服务关闭请求已接收；任务队列已停止接收新任务，HTTP server 将优雅退出。",
            }
        )
    )
