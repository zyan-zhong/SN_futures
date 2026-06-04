from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ManagedProxyConfigHandoffApiTest(unittest.TestCase):
    def test_docs_expose_config_handoff_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/managed-proxy/config-handoff", paths)
        self.assertIn("/api/terminal/managed-proxy/refresh-config-handoff", paths)

    def test_refresh_config_handoff_ignores_body_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api(
                "/api/terminal/managed-proxy/refresh-config-handoff",
                method="POST",
                body=json.dumps({"token": "raw-body-token-should-not-appear", "Authorization": "Bearer raw-body-token-should-not-appear"}),
            )

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(status, 200)
        self.assertNotIn("raw-body-token-should-not-appear", serialized)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_direct_refresh_config_handoff_records_setup_action_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, _ = handle_terminal_api("/api/terminal/managed-proxy/refresh-config-handoff", method="POST", body=json.dumps({}))
            history_status, history = handle_terminal_api("/api/terminal/setup-checklist/action-history", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(history_status, 200)
        self.assertEqual(history["action_history"][0]["action_id"], "refresh_config_handoff")
        self.assertEqual(history["action_history"][0]["status"], "success")


if __name__ == "__main__":
    unittest.main()
