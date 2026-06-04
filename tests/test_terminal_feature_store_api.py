from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


def _write_market(root: str, periods: int = 30) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.date_range("2026-01-01", periods=periods, freq="D")):
        close = 200000.0 + idx * 100.0
        rows.append({"time": day.strftime("%Y-%m-%d"), "open": close - 50, "high": close + 200, "low": close - 200, "close": close, "volume": 1000 + idx})
    (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")


class TerminalFeatureStoreApiTest(unittest.TestCase):
    def test_feature_store_api_and_docs_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market(tmp)
            status_code, build_payload = handle_terminal_api(
                "/api/terminal/feature-store/build",
                method="POST",
                body={"version": "v3"},
            )
            self._wait_for_task(str(build_payload["task_id"]))
            status_code_get, status_payload = handle_terminal_api(
                "/api/terminal/feature-store/status",
                method="GET",
                query={"version": ["v3"]},
            )
            for _ in range(200):
                if status_payload.get("status") == "success":
                    break
                time.sleep(0.05)
                status_code_get, status_payload = handle_terminal_api(
                    "/api/terminal/feature-store/status",
                    method="GET",
                    query={"version": ["v3"]},
                )
            docs_code, docs = handle_terminal_api("/api/terminal/docs", method="GET")

        self.assertEqual(status_code, 200)
        self.assertEqual(status_code_get, 200)
        self.assertEqual(docs_code, 200)
        self.assertEqual(build_payload["kind"], "build_feature_store")
        self.assertEqual(status_payload["status"], "success")
        paths = {entry.get("path") for entry in docs.get("endpoints", [])}
        self.assertIn("/api/terminal/feature-store/build", paths)
        self.assertIn("/api/terminal/feature-store/status", paths)

    def _wait_for_task(self, task_id: str) -> None:
        for _ in range(600):
            _, payload = handle_terminal_api("/api/terminal/tasks/status", method="GET", query={"id": [task_id]})
            if payload.get("status") in {"success", "failed"}:
                time.sleep(0.1)
                return
            time.sleep(0.05)


if __name__ == "__main__":
    unittest.main()
