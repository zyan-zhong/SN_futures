from __future__ import annotations

import socket
import time
from urllib.request import urlopen

from .services.process_lifecycle_service import (
    get_process_status,
    mark_server_shutdown,
    request_server_shutdown,
    write_server_runtime_files,
)


def choose_available_port(host: str = "127.0.0.1", preferred: int = 8765, end: int = 8769) -> int:
    """Return the first bindable local port in the requested inclusive range."""

    for port in range(int(preferred), int(end) + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
            except OSError:
                continue
            return port
    raise RuntimeError(f"No available port in range {preferred}-{end} on {host}")


def wait_for_server(url: str, timeout: float = 30.0, interval: float = 0.25) -> bool:
    """Poll a local HTTP endpoint until it responds or the timeout elapses."""

    deadline = time.monotonic() + float(timeout)
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=min(2.0, max(0.1, float(interval) * 4))) as response:
                if 200 <= int(response.status) < 500:
                    return True
        except Exception:
            time.sleep(float(interval))
    return False


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Start the existing ThreadingHTTPServer entrypoint."""

    from .api_server import run_api_server

    run_api_server(host=host, port=port)

__all__ = [
    "choose_available_port",
    "get_process_status",
    "mark_server_shutdown",
    "request_server_shutdown",
    "run_server",
    "wait_for_server",
    "write_server_runtime_files",
]
