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


class ManagedProxyConfigWizardApiTest(unittest.TestCase):
    def test_docs_list_config_wizard_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/config-wizard", paths)
        self.assertIn("/api/terminal/managed-proxy/refresh-config-wizard", paths)

    def test_get_config_wizard_returns_sanitized_report(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_managed_proxy_config_wizard",
            return_value={
                "status": "ready",
                "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
                "token_configured": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/config-wizard", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "ready")
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_post_refresh_wizard_ignores_raw_token_body_and_does_not_trigger_downstream(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.api.terminal_api.check_managed_proxy_health"
        ) as health, patch("sn_futures.api.terminal_api.build_managed_audit_manifest") as audit, patch(
            "sn_futures.api.terminal_api.build_feature_store_v12"
        ) as fs:
            body = json.dumps({"SN_MANAGED_PROXY_TOKEN": "managed-secret-token", "raw_token": "managed-secret-token"})
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/refresh-config-wizard", method="POST", body=body)
            secrets_file = Path(tmp) / "config" / "secrets.json"

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(status, 200)
        self.assertNotIn("managed-secret-token", serialized)
        self.assertFalse(secrets_file.exists())
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        health.assert_not_called()
        audit.assert_not_called()
        fs.assert_not_called()


if __name__ == "__main__":
    unittest.main()
