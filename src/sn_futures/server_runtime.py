from __future__ import annotations

import socket
import time
from urllib.request import urlopen


def is_port_available(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.settimeout(0.2)
        try:
            sock.bind((host, port))
        except OSError:
            return False
    return True


def choose_available_port(host: str = "127.0.0.1", preferred: int = 8765, end: int = 8769) -> int:
    for port in range(preferred, end + 1):
        if is_port_available(host, port):
            return port
    raise RuntimeError(f"{preferred}-{end} 端口均被占用，请关闭旧实例后重试。")


def wait_for_server(url: str, timeout: float = 20.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=2) as response:
                if 200 <= response.status < 500:
                    return True
        except Exception:
            time.sleep(0.4)
    return False


def run_server(host: str = "127.0.0.1", port: int = 8765) -> None:
    from .api_server import run_api_server

    run_api_server(host=host, port=port)
