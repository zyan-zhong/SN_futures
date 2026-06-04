from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class SetupActionRunLedgerApiTest(unittest.TestCase):
    def test_docs_list_setup_action_history_and_telemetry(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/setup-checklist/action-history", paths)
        self.assertIn("/api/terminal/setup-checklist/action-telemetry", paths)

    def test_run_safe_action_records_history_visible_through_api(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, run_payload = handle_terminal_api(
                "/api/terminal/setup-checklist/run-safe-action",
                method="POST",
                body=json.dumps({"action_id": "refresh_operator_runbook"}),
            )
            history_status, history = handle_terminal_api("/api/terminal/setup-checklist/action-history", method="GET")
            telemetry_status, telemetry = handle_terminal_api("/api/terminal/setup-checklist/action-telemetry", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(run_payload["setup_action_run"]["run_type"], "safe_setup_action")
        self.assertEqual(history_status, 200)
        self.assertEqual(history["action_history"][0]["action_id"], "refresh_operator_runbook")
        self.assertEqual(telemetry_status, 200)
        self.assertEqual(telemetry["latest_action"], "refresh_operator_runbook")
        self.assertFalse(telemetry["training_invoked"])
        self.assertFalse(telemetry["active_updated"])
        self.assertFalse(telemetry["customer_prediction_generated"])

    def test_unsafe_action_rejected_and_not_recorded_as_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api(
                "/api/terminal/setup-checklist/run-safe-action",
                method="POST",
                body=json.dumps({"action_id": "build_feature_store_v12"}),
            )
            _, history = handle_terminal_api("/api/terminal/setup-checklist/action-history", method="GET")

        self.assertEqual(status, 400)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(history["successful_action_count"], 0)
        self.assertEqual(history["action_history"], [])


if __name__ == "__main__":
    unittest.main()
