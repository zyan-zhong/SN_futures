from __future__ import annotations

import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api  # noqa: E402


class PredictionWorkspaceStatusApiTest(unittest.TestCase):
    def test_docs_expose_read_only_prediction_workspace_status(self) -> None:
        endpoints = {(entry["method"], entry["path"]) for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn(("GET", "/api/terminal/prediction-workspace/status"), endpoints)
        self.assertNotIn(("POST", "/api/terminal/prediction-workspace/status"), endpoints)

    def test_status_endpoint_is_read_only_and_does_not_generate_prediction(self) -> None:
        expected = {
            "status": "blocked",
            "prediction_status": "blocked",
            "prediction_generation_allowed": False,
            "active_publish_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
        with patch("sn_futures.api.terminal_api.build_prediction_workspace_status", return_value=expected, create=True):
            status, payload = handle_terminal_api("/api/terminal/prediction-workspace/status", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["prediction_status"], "blocked")
        self.assertFalse(payload["prediction_generation_allowed"])
        self.assertFalse(payload["active_publish_allowed"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
