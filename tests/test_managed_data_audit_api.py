from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedDataAuditApiTest(unittest.TestCase):
    def test_docs_list_audit_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/audit", paths)
        self.assertIn("/api/terminal/managed-proxy/run-audit", paths)
        self.assertIn("/api/terminal/managed-proxy/audit-readiness", paths)

    def test_get_audit_returns_latest_manifest(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_latest_managed_audit_manifest",
            return_value={
                "status": "blocked",
                "audit_version": "pit_v1",
                "blocking_reasons": ["managed_proxy_disabled"],
                "token_configured": True,
                "token_masked": "ma***en",
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/audit", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["audit_version"], "pit_v1")
        self.assertIs(payload["token_configured"], True)
        self.assertEqual(payload["token_masked"], "ma***en")

    def test_post_run_audit_does_not_train_or_publish(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_managed_audit_manifest",
            return_value={
                "status": "blocked",
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/run-audit", method="POST", body=json.dumps({}))

        self.assertEqual(status, 200)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_get_audit_readiness_exposes_v12_gate(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.compute_managed_audit_readiness",
            return_value={
                "status": "blocked",
                "ready": False,
                "v12_allowed": False,
                "blocking_reasons": ["missing_asof_date"],
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/managed-proxy/audit-readiness", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["ready"])
        self.assertFalse(payload["v12_allowed"])
        self.assertIn("missing_asof_date", payload["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
