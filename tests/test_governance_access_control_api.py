from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api  # noqa: E402


class GovernanceAccessControlApiTest(unittest.TestCase):
    def test_docs_expose_access_control_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/governance/access-control", paths)
        self.assertIn("/api/terminal/governance/refresh-access-control", paths)

    def test_get_access_control_reads_report_without_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_access_control_report",
            return_value={
                "status": "guarded",
                "active_write_allowed": False,
                "customer_prediction_write_allowed": False,
                "training_invoked": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/governance/access-control", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["active_write_allowed"])
        self.assertFalse(payload["customer_prediction_write_allowed"])
        self.assertFalse(payload["training_invoked"])

    def test_refresh_access_control_is_safe_refresh_only(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.refresh_access_control_report",
            return_value={
                "status": "guarded",
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/governance/refresh-access-control",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
