from __future__ import annotations

import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedDataQualityApiTest(unittest.TestCase):
    def test_docs_list_data_quality_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/data-quality", paths)
        self.assertIn("/api/terminal/managed-proxy/refresh-data-quality", paths)

    def test_get_data_quality_returns_latest_scorecard(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_managed_data_quality_scorecard",
            return_value={"status": "blocked", "gate_passed": False, "training_invoked": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/data-quality", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["training_invoked"])

    def test_refresh_data_quality_does_not_start_task_or_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_managed_data_quality_scorecard",
            return_value={"status": "blocked", "gate_passed": False, "training_invoked": False, "active_updated": False, "customer_prediction_generated": False},
            create=True,
        ), patch("sn_futures.api.terminal_api.start_task") as start_task:
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/refresh-data-quality", method="POST")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["training_invoked"])
        start_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()
