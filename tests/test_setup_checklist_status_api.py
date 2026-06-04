from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class SetupChecklistStatusApiTest(unittest.TestCase):
    def test_docs_list_setup_checklist_status_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/setup-checklist/status", paths)
        self.assertIn("/api/terminal/setup-checklist/run-safe-action", paths)

    def test_get_setup_checklist_status_returns_current_step(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_setup_checklist_status",
            return_value={
                "status": "blocked",
                "current_step": "configure_local_api_provider_credentials",
                "enabled_safe_actions": ["refresh_provider_credentials"],
                "locked_steps": ["run_provider_smoke"],
                "prediction_generation_allowed": False,
                "feature_store_v12_allowed": False,
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/setup-checklist/status", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["current_step"], "configure_local_api_provider_credentials")
        self.assertFalse(payload["prediction_generation_allowed"])
        self.assertFalse(payload["feature_store_v12_allowed"])

    def test_unsafe_action_is_rejected_without_side_effects(self) -> None:
        with patch("sn_futures.api.terminal_api.build_feature_store_v12") as build_v12, patch(
            "sn_futures.api.terminal_api.run_candidate_v12_research"
        ) as candidate_v12, patch("sn_futures.api.terminal_api.promote_candidate") as promote:
            status, payload = handle_terminal_api(
                "/api/terminal/setup-checklist/run-safe-action",
                method="POST",
                body=json.dumps({"action_id": "build_feature_store_v12"}),
            )

        self.assertEqual(status, 400)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["action_id"], "build_feature_store_v12")
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        build_v12.assert_not_called()
        candidate_v12.assert_not_called()
        promote.assert_not_called()

    def test_safe_operator_runbook_action_returns_status_snapshot(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.run_setup_checklist_safe_action",
            return_value={
                "status": "success",
                "action_id": "refresh_operator_runbook",
                "action_result": {"status": "ready"},
                "checklist_status": {
                    "status": "blocked",
                    "current_step": "configure_local_api_provider_credentials",
                    "prediction_generation_allowed": False,
                    "feature_store_v12_allowed": False,
                },
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/setup-checklist/run-safe-action",
                method="POST",
                body=json.dumps({"action_id": "refresh_operator_runbook"}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["action_id"], "refresh_operator_runbook")
        self.assertEqual(payload["checklist_status"]["current_step"], "configure_local_api_provider_credentials")
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_sample_fixture_safe_action_does_not_unlock_v12(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.run_setup_checklist_safe_action",
            return_value={
                "status": "success",
                "action_id": "run_sample_fixture_contract",
                "action_result": {
                    "status": "ready",
                    "sample_data_used": True,
                    "production_eligible": False,
                    "feature_store_v12_allowed": False,
                },
                "checklist_status": {"feature_store_v12_allowed": False, "prediction_generation_allowed": False},
                "training_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/setup-checklist/run-safe-action",
                method="POST",
                body=json.dumps({"action_id": "run_sample_fixture_contract"}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["action_result"]["feature_store_v12_allowed"])
        self.assertFalse(payload["checklist_status"]["feature_store_v12_allowed"])
        self.assertFalse(payload["checklist_status"]["prediction_generation_allowed"])


if __name__ == "__main__":
    unittest.main()
