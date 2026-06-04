from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class TerminalManagedProxyHealthApiTest(unittest.TestCase):
    def test_docs_list_managed_proxy_health_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/health", paths)
        self.assertIn("/api/terminal/managed-proxy/check", paths)
        self.assertIn("/api/terminal/managed-proxy/readiness", paths)

    def test_get_health_returns_sanitized_payload(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_managed_proxy_health",
            return_value={
                "status": "blocked",
                "provider_status": "disabled",
                "token_configured": True,
                "token_masked": "ma***en",
                "blocking_reasons": ["managed_proxy_disabled"],
                "v12_allowed": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/health", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["provider_status"], "disabled")
        self.assertIs(payload["token_configured"], True)
        self.assertEqual(payload["token_masked"], "ma***en")
        self.assertFalse(payload["v12_allowed"])

    def test_post_check_uses_health_check_not_training(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.check_managed_proxy_health",
            return_value={
                "status": "blocked",
                "provider_status": "schema_missing_fields",
                "blocking_reasons": ["managed_proxy_schema_missing_fields"],
                "active_model_written": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/check", method="POST", body=json.dumps({"force": True}))

        self.assertEqual(status, 200)
        self.assertEqual(payload["provider_status"], "schema_missing_fields")
        self.assertFalse(payload["active_model_written"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_get_readiness_exposes_v12_gate(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_managed_proxy_readiness",
            return_value={
                "status": "blocked",
                "ready": False,
                "v12_allowed": False,
                "blocking_reasons": ["managed_proxy_token_missing"],
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/readiness", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["ready"])
        self.assertFalse(payload["v12_allowed"])

    def test_feature_store_v12_build_uses_managed_proxy_gate(self) -> None:
        with patch("sn_futures.api.terminal_api.build_feature_store_v12", return_value={"version": "v12", "status": "blocked"}, create=True), patch(
            "sn_futures.api.terminal_api.start_task"
        ) as start_task:
            start_task.side_effect = lambda kind, fn=None, payload=None: {
                "task_id": "feature-store-v12-test",
                "kind": kind,
                "status": "queued",
                "payload": payload or {},
            }

            status, payload = handle_terminal_api("/api/terminal/feature-store/build", method="POST", body=json.dumps({"version": "v12"}))

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "build_feature_store")
        self.assertEqual(payload["payload"]["version"], "v12")
        self.assertFalse(payload["payload"].get("active_publish", False))


if __name__ == "__main__":
    unittest.main()
