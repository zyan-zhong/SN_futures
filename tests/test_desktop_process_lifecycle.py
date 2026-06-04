from __future__ import annotations

import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, "src")

from sn_futures.server_runtime import choose_available_port


def _get_json(url: str, timeout: float = 2.0) -> dict:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict | None = None, timeout: float = 2.0) -> dict:
    data = json.dumps(payload or {}).encode("utf-8")
    request = Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_json(url: str, timeout: float = 15.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            return _get_json(url, timeout=1.0)
        except Exception as exc:  # pragma: no cover - exercised on slow CI.
            last_error = exc
            time.sleep(0.2)
    raise AssertionError(f"server did not become ready: {last_error}")


def _port_is_open(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(0.5)
        return sock.connect_ex(("127.0.0.1", port)) == 0


class DesktopProcessLifecycleTest(unittest.TestCase):
    def test_shutdown_api_exits_backend_process_and_releases_port(self) -> None:
        port = choose_available_port(preferred=8890, end=8899)
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env["SN_DATA_DIR"] = tmp
            env["PYTHONPATH"] = str(Path("src").resolve())
            env["SN_DISABLE_AUTO_SCHEDULER"] = "1"
            proc = subprocess.Popen(
                [
                    sys.executable,
                    "-c",
                    (
                        "from sn_futures.api_server import run_api_server; "
                        f"run_api_server(host='127.0.0.1', port={port})"
                    ),
                ],
                cwd=Path.cwd(),
                env=env,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            try:
                status = _wait_for_json(f"http://127.0.0.1:{port}/api/terminal/system/process-status")
                self.assertEqual(status["pid"], proc.pid)
                self.assertTrue(status["pid_file_exists"])
                self.assertTrue(status["pid_running"])
                self.assertTrue(_port_is_open(port))

                shutdown = _post_json(f"http://127.0.0.1:{port}/api/terminal/system/shutdown", {"reason": "unit-test"})
                self.assertIn(shutdown["status"], {"shutdown_requested", "shutdown_marked"})
                self.assertFalse(shutdown["accepting_new_tasks"])
                self.assertTrue(shutdown["http_shutdown_scheduled"])

                proc.wait(timeout=10)
                self.assertNotEqual(proc.poll(), None)
                deadline = time.monotonic() + 5
                while time.monotonic() < deadline and _port_is_open(port):
                    time.sleep(0.2)
                self.assertFalse(_port_is_open(port))
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()


if __name__ == "__main__":
    unittest.main()
