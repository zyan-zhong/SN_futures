from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class CandidateV10RemediationPreflightApiTest(unittest.TestCase):
    def test_docs_expose_preflight_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/v10-remediation-preflight", paths)
        self.assertIn("/api/terminal/research/refresh-v10-remediation-preflight", paths)

    def test_get_preflight_is_read_only(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_v10_remediation_preflight",
            return_value={"status": "blocked", "training_invoked": False, "active_updated": False, "customer_prediction_generated": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/v10-remediation-preflight", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_refresh_preflight_does_not_train_or_publish(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_remediation_preflight",
            return_value={"status": "ready", "training_invoked": False, "active_updated": False, "customer_prediction_generated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/refresh-v10-remediation-preflight",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
