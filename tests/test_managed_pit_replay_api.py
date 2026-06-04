from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedPitReplayApiTest(unittest.TestCase):
    def test_docs_list_pit_replay_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/pit-replay", paths)
        self.assertIn("/api/terminal/managed-proxy/run-pit-replay", paths)

    def test_get_pit_replay_returns_latest_report(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_pit_replay_report",
            return_value={
                "status": "blocked",
                "cases_run": 0,
                "cases_passed": 0,
                "cases_failed": 0,
                "point_in_time_join_ready": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/pit-replay", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["point_in_time_join_ready"])

    def test_run_pit_replay_does_not_start_training_or_v12_task(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.run_pit_replay_harness",
            return_value={
                "status": "blocked",
                "cases_run": 0,
                "cases_passed": 0,
                "cases_failed": 0,
                "point_in_time_join_ready": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ), patch("sn_futures.api.terminal_api.start_task") as start_task, patch(
            "sn_futures.api.terminal_api.build_feature_store_v12"
        ) as build_v12:
            status, payload = handle_terminal_api(
                "/api/terminal/managed-proxy/run-pit-replay",
                method="POST",
                body=json.dumps({"force": True}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        start_task.assert_not_called()
        build_v12.assert_not_called()


if __name__ == "__main__":
    unittest.main()
