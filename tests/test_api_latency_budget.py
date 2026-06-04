from __future__ import annotations

import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.api_response_cache import clear_api_response_cache


class ApiLatencyBudgetTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_api_response_cache()

    def _measure(self, path: str) -> tuple[float, int, dict]:
        started = time.perf_counter()
        status, payload = handle_terminal_api(path)
        return (time.perf_counter() - started) * 1000, status, payload

    def test_light_api_budget_contract(self) -> None:
        budgets = {
            "/api/terminal/summary": 300.0,
            "/api/terminal/system-health": 300.0,
            "/api/terminal/snapshot-lite": 500.0,
        }

        for path, budget_ms in budgets.items():
            with self.subTest(path=path):
                duration_ms, status, payload = self._measure(path)
                self.assertEqual(status, 200)
                self.assertLess(duration_ms, budget_ms)
                self.assertIn("generated_at", payload)
                self.assertIn("cache_age_seconds", payload)

    def test_system_health_does_not_run_provider_checks(self) -> None:
        with patch("sn_futures.v2_api.get_system_truth_audit", side_effect=AssertionError("slow provider called")):
            status, payload = handle_terminal_api("/api/terminal/system-health")

        self.assertEqual(status, 200)
        self.assertEqual(payload.get("mode"), "lightweight")
        self.assertEqual(payload.get("truth_audit", {}).get("status"), "skipped")

    def test_snapshot_lite_cache_hit_on_second_call(self) -> None:
        first_status, first_payload = handle_terminal_api("/api/terminal/snapshot-lite")
        second_status, second_payload = handle_terminal_api("/api/terminal/snapshot-lite")

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertFalse(first_payload.get("cache_hit"))
        self.assertTrue(second_payload.get("cache_hit"))


if __name__ == "__main__":
    unittest.main()
