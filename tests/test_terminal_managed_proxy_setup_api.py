from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class TerminalManagedProxySetupApiTest(unittest.TestCase):
    def test_docs_list_managed_proxy_setup_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/setup", paths)
        self.assertIn("/api/terminal/managed-proxy/refresh-setup", paths)
        self.assertIn("/api/terminal/managed-proxy/endpoint-contract", paths)
        self.assertIn("/api/terminal/managed-proxy/run-contract-dry-run", paths)

    def test_get_setup_returns_sanitized_status(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_managed_proxy_setup_status",
            return_value={
                "status": "blocked",
                "token_configured": True,
                "token_masked": "ma***en",
                "blocking_reasons": ["managed_proxy_base_url_missing"],
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/setup", method="GET")

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(status, 200)
        self.assertTrue(payload["token_configured"])
        self.assertEqual(payload["token_masked"], "ma***en")
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertNotIn("Authorization", serialized)

    def test_post_refresh_setup_does_not_trigger_downstream_tasks(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.refresh_managed_proxy_setup",
            return_value={
                "status": "blocked",
                "next_allowed_action": "configure_managed_proxy_token",
                "feature_store_v12_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/refresh-setup", method="POST", body="{}")

        self.assertEqual(status, 200)
        self.assertEqual(payload["next_allowed_action"], "configure_managed_proxy_token")
        self.assertFalse(payload["feature_store_v12_allowed"])
        self.assertFalse(payload["training_invoked"])

    def test_post_contract_dry_run_returns_setup_report_not_task(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.run_managed_proxy_schema_dry_run",
            return_value={
                "status": "blocked",
                "schema_contract_status": "blocked",
                "pit_timestamp_contract_status": "not_run",
                "blocking_reasons": ["managed_proxy_schema_missing_fields"],
                "managed_proxy_health_allowed": False,
                "feature_store_v12_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/run-contract-dry-run", method="POST", body="{}")

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_contract_status"], "blocked")
        self.assertNotIn("task_id", payload)
        self.assertFalse(payload["training_invoked"])


if __name__ == "__main__":
    unittest.main()
