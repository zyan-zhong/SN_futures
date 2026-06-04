from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.setup_action_run_ledger_service import (
    get_setup_action_history,
    summarize_setup_action_telemetry,
)
from sn_futures.services.setup_checklist_status_service import build_setup_checklist_status, run_setup_checklist_safe_action
from sn_futures.services.task_notification_service import build_task_notifications


class SetupActionRunLedgerServiceTest(unittest.TestCase):
    def test_refresh_operator_runbook_records_safe_setup_action_entry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            result = run_setup_checklist_safe_action("refresh_operator_runbook")
            history = get_setup_action_history()
            telemetry = summarize_setup_action_telemetry()

        self.assertEqual(result["status"], "success")
        self.assertEqual(history["status"], "ready")
        self.assertEqual(history["action_history"][0]["run_type"], "safe_setup_action")
        self.assertEqual(history["action_history"][0]["action_scope"], "setup_checklist")
        self.assertEqual(history["action_history"][0]["action_id"], "refresh_operator_runbook")
        self.assertEqual(history["action_history"][0]["status"], "success")
        self.assertIn("training", history["action_history"][0]["forbidden_side_effects"])
        self.assertFalse(history["action_history"][0]["training_invoked"])
        self.assertFalse(history["action_history"][0]["active_updated"])
        self.assertFalse(history["action_history"][0]["customer_prediction_generated"])
        self.assertEqual(telemetry["latest_action"], "refresh_operator_runbook")
        self.assertEqual(telemetry["latest_action_status"], "success")
        self.assertEqual(telemetry["ledger_status"], "ready")
        self.assertEqual(telemetry["history_count"], 1)
        self.assertEqual(telemetry["current_step"], "configure_local_api_provider_credentials")

    def test_sample_fixture_action_records_success_without_unlocking_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            result = run_setup_checklist_safe_action("run_sample_fixture_contract")
            history = get_setup_action_history()
            telemetry = summarize_setup_action_telemetry()

        self.assertEqual(history["action_history"][0]["action_id"], "run_sample_fixture_contract")
        self.assertFalse(result.get("feature_store_v12_allowed", True))
        self.assertFalse(result["checklist_status"]["feature_store_v12_allowed"])
        self.assertFalse(telemetry["feature_store_v12_allowed"])
        self.assertFalse(telemetry["customer_prediction_generated"])

    def test_failed_safe_action_records_failure_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True), patch(
            "sn_futures.services.setup_checklist_status_service.refresh_schema_mapping_report",
            side_effect=RuntimeError("schema mapping failed because endpoint unavailable"),
        ):
            result = run_setup_checklist_safe_action("refresh_schema_mapping")
            history = get_setup_action_history()

        self.assertEqual(result["status"], "failed")
        self.assertIn("schema mapping failed", result["blocking_reasons"][0])
        self.assertEqual(history["action_history"][0]["status"], "failed")
        self.assertIn("schema mapping failed", history["action_history"][0]["blocking_reasons"][0])
        self.assertFalse(history["action_history"][0]["training_invoked"])
        self.assertFalse(history["action_history"][0]["active_updated"])
        self.assertFalse(history["action_history"][0]["customer_prediction_generated"])

    def test_unsafe_action_does_not_create_successful_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            result = run_setup_checklist_safe_action("build_feature_store_v12")
            history = get_setup_action_history()

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(history["action_history"], [])
        self.assertEqual(history["successful_action_count"], 0)

    def test_history_sanitizes_secret_like_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True), patch(
            "sn_futures.services.setup_checklist_status_service.refresh_managed_proxy_setup",
            return_value={
                "status": "blocked",
                "warning_reasons": ["Authorization: Bearer raw-secret-token"],
                "token": "raw-secret-token",
                "endpoint": "https://example.invalid/private?token=raw-secret-token",
            },
        ):
            run_setup_checklist_safe_action("refresh_managed_proxy_setup")
            history = get_setup_action_history()
            serialized = json.dumps(history, ensure_ascii=False)

        self.assertNotIn("raw-secret-token", serialized)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("Bearer", serialized)
        self.assertNotIn("https://example.invalid/private", serialized)

    def test_checklist_status_and_task_notifications_include_setup_action_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            run_setup_checklist_safe_action("refresh_operator_runbook")
            checklist = build_setup_checklist_status()
            notifications = build_task_notifications()

        self.assertEqual(checklist["setup_action_telemetry"]["latest_action"], "refresh_operator_runbook")
        self.assertEqual(notifications["setup_action_history"]["latest_action"], "refresh_operator_runbook")
        self.assertFalse(notifications["setup_action_history"]["is_prediction_failure"])
        self.assertFalse(notifications["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
