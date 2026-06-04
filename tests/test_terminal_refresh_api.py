from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.json_utils import safe_json_dumps
from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api
from sn_futures.services.terminal_service import build_terminal_snapshot


class TerminalRefreshApiTest(unittest.TestCase):
    def test_refresh_status_endpoint_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/refresh/status", "GET", {}, None)

        self.assertEqual(status, 200)
        self.assertIn("status", payload)
        safe_json_dumps(payload)

    def test_refresh_docs_are_listed(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}
        self.assertIn("/api/terminal/refresh/all", paths)
        self.assertIn("/api/terminal/refresh/status", paths)
        self.assertIn("/api/terminal/refresh/history", paths)
        self.assertIn("/api/terminal/tasks/start", paths)

    def test_refresh_news_post_returns_async_task_without_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": ""},
            clear=False,
        ):
            status, payload = handle_terminal_api("/api/terminal/refresh/news", "POST", {}, "{}")
            self._wait_for_task(str(payload["task_id"]))

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "refresh_news")
        self.assertIn(payload["status"], {"queued", "running", "success"})
        self.assertIn("task_id", payload)
        self.assertNotIn("steps", payload)

    def test_snapshot_is_lite_and_does_not_embed_heavy_refresh_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            snapshot = build_terminal_snapshot()

        self.assertEqual(snapshot.get("snapshot_mode"), "lite")
        self.assertIn("summary", snapshot)
        self.assertNotIn("data_status", snapshot)
        safe_json_dumps(snapshot)

    def _wait_for_task(self, task_id: str) -> None:
        for _ in range(40):
            _, payload = handle_terminal_api("/api/terminal/tasks/status", "GET", query={"id": [task_id]})
            if payload.get("status") in {"success", "failed"}:
                time.sleep(0.05)
                return
            time.sleep(0.025)


if __name__ == "__main__":
    unittest.main()
