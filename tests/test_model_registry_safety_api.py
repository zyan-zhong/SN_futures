from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ModelRegistrySafetyApiTest(unittest.TestCase):
    def test_docs_expose_model_registry_safety_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/model-registry-safety", paths)
        self.assertIn("/api/terminal/research/refresh-model-registry-safety", paths)

    def test_get_model_registry_safety_does_not_write_active(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_model_registry_safety_report",
            return_value={"status": "blocked", "active_write_allowed": False, "active_updated": False, "customer_prediction_generated": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/model-registry-safety", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["active_write_allowed"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_refresh_model_registry_safety_is_report_only(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_registry_safety_report",
            return_value={"status": "blocked", "active_write_allowed": False, "active_updated": False, "customer_prediction_generated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/refresh-model-registry-safety",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
