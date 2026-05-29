from __future__ import annotations

import json
import os
import socket
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import psutil

from ..runtime import get_user_data_dir


APP_VERSION = "V3.8.0"
BUILD_ID = "sn-terminal-v3.8.0"
LOCK_FILE = "sn_terminal.lock"
STATE_FILE = "runtime_state.json"


@dataclass
class RuntimeState:
    build_id: str
    app_version: str
    active_pid: int
    api_port: int
    frontend_port: int
    data_dir: str
    cache_dir: str
    model_registry_path: str
    started_at: float
    message: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SingleInstanceLock:
    """Cross-process lock based on an exclusive lock file handle.

    This is intentionally small and dependency-light.  The handle is kept open
    for the lifetime of the desktop process.  Child API/worker processes do not
    acquire this lock; the desktop launcher is the single-instance owner.
    """

    def __init__(self, lock_path: Path | None = None) -> None:
        self.lock_path = lock_path or (runtime_dir() / LOCK_FILE)
        self._handle: Any | None = None

    def acquire(self) -> bool:
        self.lock_path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.lock_path.open("a+b")
        try:
            import msvcrt

            msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            self._handle.seek(0)
            self._handle.truncate()
            self._handle.write(str(os.getpid()).encode("ascii", errors="ignore"))
            self._handle.flush()
            return True
        except OSError:
            try:
                self._handle.close()
            except Exception:
                pass
            self._handle = None
            return False

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            import msvcrt

            self._handle.seek(0)
            msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
        except OSError:
            pass
        try:
            self._handle.close()
        finally:
            self._handle = None


def runtime_dir() -> Path:
    target = get_user_data_dir() / "runtime"
    target.mkdir(parents=True, exist_ok=True)
    return target


def state_path() -> Path:
    return runtime_dir() / STATE_FILE


def default_cache_dir() -> Path:
    target = get_user_data_dir() / "cache"
    target.mkdir(parents=True, exist_ok=True)
    return target


def model_registry_path() -> Path:
    target = get_user_data_dir() / "models" / BUILD_ID / "model_registry.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    return target


def read_runtime_state() -> dict[str, Any]:
    path = state_path()
    if not path.exists():
        return {}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def write_runtime_state(api_port: int = 8765, frontend_port: int = 8765, message: str = "") -> RuntimeState:
    state = RuntimeState(
        build_id=BUILD_ID,
        app_version=APP_VERSION,
        active_pid=os.getpid(),
        api_port=int(api_port),
        frontend_port=int(frontend_port),
        data_dir=str(get_user_data_dir()),
        cache_dir=str(default_cache_dir()),
        model_registry_path=str(model_registry_path()),
        started_at=time.time(),
        message=message,
    )
    state_path().write_text(json.dumps(state.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    return state


def pid_is_running(pid: int | str | None) -> bool:
    try:
        return psutil.pid_exists(int(pid or 0))
    except Exception:
        return False


def port_owner_pid(port: int) -> int | None:
    try:
        for conn in psutil.net_connections(kind="inet"):
            if conn.laddr and conn.laddr.port == int(port) and conn.pid:
                return int(conn.pid)
    except Exception:
        return None
    return None


def choose_api_port(default: int = 8765) -> int:
    env_port = os.environ.get("SN_TERMINAL_API_PORT")
    if env_port:
        try:
            return int(env_port)
        except ValueError:
            pass
    owner = port_owner_pid(default)
    if owner and owner != os.getpid():
        return default
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        try:
            sock.bind(("127.0.0.1", default))
            return default
        except OSError:
            return default


def runtime_status() -> dict[str, Any]:
    state = read_runtime_state()
    state.setdefault("build_id", BUILD_ID)
    state.setdefault("app_version", APP_VERSION)
    state["state_file"] = str(state_path())
    state["lock_file"] = str(runtime_dir() / LOCK_FILE)
    state["active_pid_running"] = pid_is_running(state.get("active_pid"))
    port = int(state.get("api_port") or os.environ.get("SN_TERMINAL_API_PORT") or 8765)
    state["port_owner_pid"] = port_owner_pid(port)
    return state
