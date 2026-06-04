from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.api_response_cache import get_cached_response, set_cached_response
from sn_futures.services.cache_invalidation_service import invalidate_after_task
from sn_futures.services.data_watermark_service import get_data_watermark_report, update_data_watermark
from sn_futures.services.task_queue_service import start_task


class DataFreshnessConsistencyTest(unittest.TestCase):
    def test_watermark_api_exposes_consistent_mode_and_cache_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            update_data_watermark("market", source="unit-test")
            status, payload = handle_terminal_api("/api/terminal/data-watermark")

        self.assertEqual(status, 200)
        self.assertIn("market_data_updated_at", payload)
        self.assertIn(payload["current_data_mode"], {"real", "cache", "sample", "mixed"})
        self.assertIn("freshness_summary", payload)

    def test_refresh_task_completion_invalidates_terminal_cache_and_updates_watermark(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            set_cached_response("terminal:summary", {"probe": "cached"})
            task = start_task("refresh_market", lambda: {"status": "success"})
            for _ in range(80):
                _, status_payload = handle_terminal_api("/api/terminal/tasks/status", query={"id": [str(task["task_id"])]})
                if status_payload.get("status") in {"success", "failed"}:
                    break
                time.sleep(0.025)
            cached = get_cached_response("terminal:summary", 60)
            watermark = get_data_watermark_report()

        self.assertIsNone(cached)
        self.assertTrue(watermark["market_data_updated_at"])
        self.assertEqual(watermark["last_invalidation_reason"], "refresh_market")

    def test_manual_cache_invalidate_api_clears_cached_response(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            set_cached_response("terminal:data-status", {"probe": "cached"})
            status, payload = handle_terminal_api("/api/terminal/cache/invalidate", method="POST", body={"reason": "unit-test"})
            cached = get_cached_response("terminal:data-status", 60)

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "success")
        self.assertIsNone(cached)


if __name__ == "__main__":
    unittest.main()
