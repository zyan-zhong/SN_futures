from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api  # noqa: E402


class GovernanceObservabilityApiTest(unittest.TestCase):
    def test_docs_expose_observability_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/governance/observability", paths)
        self.assertIn("/api/terminal/governance/refresh-observability", paths)

    def test_get_observability_reads_report_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_governance_observability_report",
            return_value={
                "status": "pass",
                "slo_results": {"overall": {"status": "pass"}},
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/governance/observability", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "pass")
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_refresh_observability_is_safe_report_refresh_only(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.refresh_governance_observability_report",
            return_value={
                "status": "blocked",
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/governance/refresh-observability",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
