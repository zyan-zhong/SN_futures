from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class V10CostFailureResearchApiTest(unittest.TestCase):
    def test_docs_expose_v10_cost_remediation_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/v10-cost-remediation", paths)
        self.assertIn("/api/terminal/research/refresh-v10-cost-remediation", paths)

    def test_get_v10_cost_remediation_reads_report_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_v10_cost_failure_research_report",
            return_value={"status": "ready", "training_invoked": False, "manual_approval_recommended": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/v10-cost-remediation", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["manual_approval_recommended"])

    def test_refresh_v10_cost_remediation_is_not_task_queue_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_cost_failure_research_report",
            return_value={"status": "ready", "training_invoked": False, "active_updated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/refresh-v10-cost-remediation",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])


if __name__ == "__main__":
    unittest.main()
