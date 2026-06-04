from __future__ import annotations

import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


class TerminalApiPerformanceContractTest(unittest.TestCase):
    def test_summary_is_lightweight_cached_and_does_not_start_heavy_tasks(self) -> None:
        with patch("sn_futures.services.task_queue_service.start_task") as start_task:
            status, payload = handle_terminal_api("/api/terminal/summary")

        self.assertEqual(status, 200)
        self.assertIn("generated_at", payload)
        self.assertIn("cache_age_seconds", payload)
        self.assertFalse(payload.get("customer_prediction_generated", False))
        start_task.assert_not_called()

    def test_system_health_is_lightweight_and_does_not_call_truth_audit_provider(self) -> None:
        with patch("sn_futures.v2_api.get_system_truth_audit", side_effect=TimeoutError("slow provider")):
            status, payload = handle_terminal_api("/api/terminal/system-health")

        self.assertEqual(status, 200)
        self.assertIn("generated_at", payload)
        self.assertEqual(payload.get("health", {}).get("api_status"), "正常")
        self.assertIn("lightweight", payload.get("mode", ""))

    def test_snapshot_lite_does_not_embed_heavy_sections(self) -> None:
        status, payload = handle_terminal_api("/api/terminal/snapshot-lite")

        self.assertEqual(status, 200)
        self.assertEqual(payload.get("snapshot_mode"), "lite")
        self.assertIn("summary", payload)
        self.assertIn("generated_at", payload)
        self.assertNotIn("predictions", payload)
        self.assertNotIn("backtest_diagnostics", payload)
        self.assertNotIn("data_status", payload)


if __name__ == "__main__":
    unittest.main()
