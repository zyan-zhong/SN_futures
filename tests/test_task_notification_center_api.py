from __future__ import annotations

import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api  # noqa: E402


class TaskNotificationCenterApiTest(unittest.TestCase):
    def test_docs_expose_read_only_task_notifications(self) -> None:
        paths = {(entry["method"], entry["path"]) for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn(("GET", "/api/terminal/task-notifications"), paths)
        self.assertNotIn(("POST", "/api/terminal/task-notifications"), paths)

    def test_task_notifications_endpoint_is_read_only(self) -> None:
        expected = {
            "status": "ready",
            "toast_task": None,
            "stale_failure_suppressed": True,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
        with patch("sn_futures.api.terminal_api.build_task_notifications", return_value=expected, create=True):
            status, payload = handle_terminal_api("/api/terminal/task-notifications", method="GET")

        self.assertEqual(status, 200)
        self.assertTrue(payload["stale_failure_suppressed"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
