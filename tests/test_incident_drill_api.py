from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api  # noqa: E402


class IncidentDrillApiTest(unittest.TestCase):
    def test_docs_expose_incident_drill_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/governance/incident-drill", paths)
        self.assertIn("/api/terminal/governance/run-incident-drill", paths)
        self.assertIn("/api/terminal/governance/refresh-lockdown-state", paths)

    def test_get_incident_drill_reads_report_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_incident_drill_report",
            return_value={
                "status": "pass",
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/governance/incident-drill", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_run_incident_drill_is_simulation_only(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.run_incident_drill_simulation",
            return_value={
                "status": "pass",
                "simulated_artifacts_only": True,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/governance/run-incident-drill",
                method="POST",
                body=json.dumps({"simulation_only": True}),
            )

        self.assertEqual(status, 200)
        self.assertTrue(payload["simulated_artifacts_only"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_refresh_lockdown_state_is_safe_report_refresh(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.refresh_lockdown_state_report",
            return_value={
                "status": "ready",
                "lockdown_triggered": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/governance/refresh-lockdown-state",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
