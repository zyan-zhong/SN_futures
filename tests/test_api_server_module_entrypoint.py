from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

sys.path.insert(0, "src")

from sn_futures.server_runtime import choose_available_port


def _get_json(url: str, timeout: float = 3.0) -> dict:
    with urlopen(url, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _post_json(url: str, payload: dict | None = None, timeout: float = 3.0) -> dict:
    data = json.dumps(payload or {}).encode("utf-8")
    request = Request(url, data=data, method="POST", headers={"Content-Type": "application/json"})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def _wait_for_json(url: str, proc: subprocess.Popen, timeout: float = 20.0) -> dict:
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        if proc.poll() is not None:
            stdout, stderr = proc.communicate(timeout=2)
            raise AssertionError(
                "python -m sn_futures.api_server exited before serving requests; "
                f"returncode={proc.returncode}; stdout={stdout[-1000:]}; stderr={stderr[-1000:]}"
            )
        try:
            return _get_json(url, timeout=1.0)
        except Exception as exc:
            last_error = exc
            time.sleep(0.2)
    raise AssertionError(f"python -m sn_futures.api_server did not become ready: {last_error}")


class ApiServerModuleEntrypointTest(unittest.TestCase):
    def test_python_module_entrypoint_serves_terminal_api_and_shutdown(self) -> None:
        port = choose_available_port(preferred=8910, end=8999)
        with tempfile.TemporaryDirectory() as tmp:
            env = os.environ.copy()
            env.update(
                {
                    "PYTHONPATH": str(Path("src").resolve()),
                    "SN_DATA_DIR": tmp,
                    "SN_INSIGHT_DATA_DIR": tmp,
                    "SN_DISABLE_AUTO_SCHEDULER": "1",
                    "SN_TERMINAL_API_PORT": str(port),
                    "SN_ALPHA_VANTAGE_KEY": "",
                    "SN_NEWSAPI_KEY": "",
                    "SN_TUSHARE_TOKEN": "",
                    "SN_LOCAL_API_PROVIDER_TOKEN": "",
                    "SN_LOCAL_API_PROVIDER_ENABLED": "0",
                }
            )
            proc = subprocess.Popen(
                [sys.executable, "-m", "sn_futures.api_server"],
                cwd=Path.cwd(),
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            try:
                docs = _wait_for_json(f"http://127.0.0.1:{port}/api/terminal/docs", proc)
                data_status = _get_json(f"http://127.0.0.1:{port}/api/terminal/data-status")
                predictions = _get_json(f"http://127.0.0.1:{port}/api/terminal/predictions")

                endpoint_paths = {
                    str(item.get("path"))
                    for item in docs.get("endpoints", [])
                    if isinstance(item, dict)
                }
                self.assertEqual(docs.get("framework"), "ThreadingHTTPServer")
                self.assertIn("/api/terminal/docs", endpoint_paths)
                self.assertIn("/api/terminal/predictions", endpoint_paths)
                self.assertIn("generated_at", data_status)
                self.assertIn(predictions.get("status"), {"ok", "blocked"})
                self.assertFalse(bool(predictions.get("customer_prediction_generated", False)))

                shutdown = _post_json(
                    f"http://127.0.0.1:{port}/api/terminal/system/shutdown",
                    {"reason": "module-entrypoint-test"},
                )
                self.assertTrue(bool(shutdown.get("http_shutdown_scheduled")))
                proc.wait(timeout=10)
            finally:
                if proc.poll() is None:
                    proc.terminate()
                    try:
                        proc.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        proc.kill()
                        proc.wait(timeout=3)


if __name__ == "__main__":
    unittest.main()
