from __future__ import annotations

import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class TerminalManagedProxyReliabilityApiTest(unittest.TestCase):
    def test_docs_list_managed_proxy_reliability_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/reliability", paths)
        self.assertIn("/api/terminal/managed-proxy/run-canary", paths)

    def test_get_reliability_returns_report(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_managed_proxy_reliability_report",
            return_value={
                "status": "blocked",
                "canary_status": "not_run",
                "circuit_breaker_status": "closed",
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/reliability", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["canary_status"], "not_run")
        self.assertFalse(payload["training_invoked"])

    def test_post_run_canary_does_not_start_training_or_v12_build(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.run_managed_proxy_canary_check",
            return_value={
                "status": "blocked",
                "canary_status": "timeout",
                "circuit_breaker_status": "closed",
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ), patch("sn_futures.api.terminal_api.start_task") as start_task:
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/run-canary", method="POST")

        self.assertEqual(status, 200)
        self.assertEqual(payload["canary_status"], "timeout")
        self.assertFalse(payload["training_invoked"])
        start_task.assert_not_called()


if __name__ == "__main__":
    unittest.main()
