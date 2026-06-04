from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class CostStressAttributionApiContractTest(unittest.TestCase):
    def test_docs_expose_cost_stress_attribution_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/cost-stress-attribution", paths)
        self.assertIn("/api/terminal/research/refresh-cost-stress-attribution", paths)
        self.assertIn("/api/terminal/research/candidate-v10-report", paths)
        self.assertIn("/api/terminal/research/candidate-v12-report", paths)

    def test_get_cost_stress_attribution_reads_summary_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_cost_stress_attribution_report",
            return_value={"status": "success", "training_invoked": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/cost-stress-attribution", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])

    def test_refresh_cost_stress_attribution_calls_refresh_service_not_task_queue(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.refresh_cost_stress_attribution",
            return_value={"status": "success", "training_invoked": False, "active_updated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/refresh-cost-stress-attribution",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])


if __name__ == "__main__":
    unittest.main()
