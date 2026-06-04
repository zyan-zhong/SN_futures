from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedProxyOperatorRunbookApiTest(unittest.TestCase):
    def test_docs_list_operator_runbook_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/operator-runbook", paths)
        self.assertIn("/api/terminal/managed-proxy/refresh-operator-runbook", paths)

    def test_get_operator_runbook_returns_sanitized_report(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_operator_onboarding_runbook",
            return_value={
                "status": "ready_with_missing_config",
                "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
                "endpoint_configured": False,
                "token_configured": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/operator-runbook", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ready_with_missing_config")
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_refresh_operator_runbook_ignores_raw_token_body_and_does_not_trigger_downstream(self) -> None:
        secret = "managed-secret-token-123456"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.api.terminal_api.check_managed_proxy_health"
        ) as health, patch(
            "sn_futures.api.terminal_api.build_managed_audit_manifest"
        ) as audit, patch(
            "sn_futures.api.terminal_api.build_feature_store_v12"
        ) as fs, patch(
            "sn_futures.api.terminal_api.build_training_dataset_v12"
        ) as td, patch(
            "sn_futures.api.terminal_api.run_candidate_v12_research"
        ) as candidate:
            body = json.dumps(
                {
                    "SN_MANAGED_PROXY_TOKEN": secret,
                    "raw_token": secret,
                    "Authorization": f"Bearer {secret}",
                    "base_url": "https://endpoint.example/secret-path",
                }
            )
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/refresh-operator-runbook", method="POST", body=body)
            secrets_file = Path(tmp) / "config" / "secrets.json"

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(status, 200)
        self.assertNotIn(secret, serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertFalse(secrets_file.exists())
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        health.assert_not_called()
        audit.assert_not_called()
        fs.assert_not_called()
        td.assert_not_called()
        candidate.assert_not_called()


if __name__ == "__main__":
    unittest.main()
