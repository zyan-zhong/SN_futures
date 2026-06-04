from __future__ import annotations

import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.setup_checklist_status_service import (
    FORBIDDEN_SETUP_ACTIONS,
    SAFE_SETUP_ACTIONS,
    build_setup_checklist_status,
    validate_no_forbidden_setup_actions,
)


def _provider_credentials(*, configured: bool = False) -> dict[str, object]:
    return {
        "status": "configured" if configured else "blocked",
        "provider_mode": "local_api_provider",
        "provider_credentials_status": "configured" if configured else "missing_config",
        "configured_providers": ["twelvedata"] if configured else [],
        "missing_provider_credentials": [] if configured else ["twelvedata", "alphavantage"],
        "blocking_reasons": [] if configured else ["provider_api_key_missing"],
        "next_allowed_action": "run_provider_smoke" if configured else "configure_local_api_provider_credentials",
        "report_path": "outputs/diagnostics/local_api_provider_credentials_report.json",
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


class SetupChecklistStatusServiceTest(unittest.TestCase):
    def test_current_unconfigured_state_points_to_local_provider_credentials_step(self) -> None:
        with patch(
            "sn_futures.services.setup_checklist_status_service.get_provider_credentials_report",
            return_value=_provider_credentials(configured=False),
        ), patch(
            "sn_futures.services.setup_checklist_status_service.build_prediction_workspace_status",
            return_value={"prediction_generation_allowed": False},
        ):
            report = build_setup_checklist_status()

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["current_step"], "configure_local_api_provider_credentials")
        self.assertEqual(report["provider_mode"], "local_api_provider")
        self.assertFalse(report["prediction_generation_allowed"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertIn("refresh_provider_credentials", report["enabled_safe_actions"])
        self.assertIn("refresh_operator_runbook", report["enabled_safe_actions"])
        self.assertIn("run_sample_fixture_contract", report["enabled_safe_actions"])
        self.assertIn("run_provider_smoke", report["locked_steps"])
        self.assertIn("run_pit_audit", report["locked_steps"])
        self.assertIn("review_v12_input_contract", report["locked_steps"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_each_step_has_progress_fields_and_current_marker(self) -> None:
        with patch(
            "sn_futures.services.setup_checklist_status_service.get_provider_credentials_report",
            return_value=_provider_credentials(configured=False),
        ):
            report = build_setup_checklist_status()

        steps = report["steps"]
        self.assertGreaterEqual(len(steps), 10)
        current_steps = [step for step in steps if step["is_current_step"]]
        self.assertEqual([step["step_id"] for step in current_steps], ["configure_local_api_provider_credentials"])
        for step in steps:
            for key in [
                "step_id",
                "label",
                "status",
                "short_reason",
                "safe_action_id",
                "action_enabled",
                "action_disabled_reason",
                "evidence_path",
                "is_current_step",
            ]:
                self.assertIn(key, step)
            self.assertIn(step["status"], {"complete", "blocked", "available", "locked", "running", "failed"})

    def test_forbidden_setup_actions_are_never_allowed(self) -> None:
        for action_id in FORBIDDEN_SETUP_ACTIONS:
            result = validate_no_forbidden_setup_actions(action_id)
            self.assertEqual(result["status"], "blocked", action_id)
            self.assertIn(action_id, result["action_id"])
            self.assertFalse(result["training_invoked"])
            self.assertFalse(result["active_updated"])
            self.assertFalse(result["customer_prediction_generated"])

    def test_safe_action_inventory_excludes_forbidden_actions(self) -> None:
        overlap = set(SAFE_SETUP_ACTIONS) & set(FORBIDDEN_SETUP_ACTIONS)
        self.assertEqual(overlap, set())


if __name__ == "__main__":
    unittest.main()
