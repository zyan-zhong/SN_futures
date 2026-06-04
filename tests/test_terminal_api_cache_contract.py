from __future__ import annotations

import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.api_response_cache import clear_api_response_cache


class TerminalApiCacheContractTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_api_response_cache()

    def test_summary_second_call_is_cache_hit(self) -> None:
        first_status, first_payload = handle_terminal_api("/api/terminal/summary")
        second_status, second_payload = handle_terminal_api("/api/terminal/summary")

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertFalse(first_payload.get("cache_hit"))
        self.assertTrue(second_payload.get("cache_hit"))
        self.assertIn("cache_age_seconds", second_payload)

    def test_model_health_cached_call_does_not_rerun_provider_within_ttl(self) -> None:
        with patch("sn_futures.api.terminal_api.build_terminal_model_health", return_value={"model_status": "cached-test"}) as fn:
            first_status, first_payload = handle_terminal_api("/api/terminal/model-health")
            second_status, second_payload = handle_terminal_api("/api/terminal/model-health")

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(fn.call_count, 1)
        self.assertFalse(first_payload.get("cache_hit"))
        self.assertTrue(second_payload.get("cache_hit"))

    def test_refresh_all_returns_task_status_not_blocking_refresh_payload(self) -> None:
        with patch("sn_futures.api.terminal_api.run_institutional_refresh_all", return_value={"status": "success"}) as refresh:
            status, payload = handle_terminal_api("/api/terminal/refresh/all", method="POST", body={"force": True})
            refresh.assert_not_called()
            final = self._wait_for_task(str(payload["task_id"]))

        self.assertEqual(status, 200)
        self.assertIn(payload.get("status"), {"queued", "running", "success"})
        self.assertIn("task_id", payload)
        self.assertNotIn("steps", payload)
        self.assertEqual(final.get("status"), "success")

    def _wait_for_task(self, task_id: str) -> dict:
        for _ in range(80):
            _, payload = handle_terminal_api("/api/terminal/tasks/status", query={"id": [task_id]})
            if payload.get("status") in {"success", "failed"}:
                time.sleep(0.05)
                return payload
            time.sleep(0.025)
        return {}


if __name__ == "__main__":
    unittest.main()
