from __future__ import annotations

import os
import sys
import tempfile
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

    def test_refresh_news_post_skips_without_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": ""},
            clear=False,
        ):
            status, payload = handle_terminal_api("/api/terminal/refresh/news", "POST", {}, "{}")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["steps"][0]["status"], "skipped")
        self.assertIn("未配置 NewsAPI", payload["steps"][0]["message_zh"])

    def test_snapshot_contains_refresh_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            snapshot = build_terminal_snapshot()

        self.assertIn("data_status", snapshot)
        self.assertIn("refresh_status", snapshot)
        safe_json_dumps(snapshot)


if __name__ == "__main__":
    unittest.main()
