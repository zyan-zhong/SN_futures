from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.incident_drill_service import (  # noqa: E402
    build_incident_drill_report,
    compute_lockdown_state,
    run_incident_drill_simulation,
    simulate_endpoint_token_echo,
    simulate_forbidden_action_exposure,
    simulate_secret_leak_detection,
    simulate_unapproved_active_model,
    simulate_unapproved_customer_predictions,
)


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class IncidentDrillServiceTest(unittest.TestCase):
    def test_secret_leak_scenario_triggers_lockdown_without_raw_token(self) -> None:
        scenario = simulate_secret_leak_detection()

        self.assertTrue(scenario["lockdown_triggered"])
        self.assertEqual(scenario["scenario"], "secret_leak_detected")
        self.assertNotIn("0ad377e", json.dumps(scenario, ensure_ascii=False))

    def test_endpoint_echo_token_triggers_lockdown_without_raw_token(self) -> None:
        scenario = simulate_endpoint_token_echo()

        self.assertTrue(scenario["lockdown_triggered"])
        self.assertEqual(scenario["scenario"], "endpoint_echoed_token")
        self.assertNotIn("Bearer raw", json.dumps(scenario, ensure_ascii=False))

    def test_unapproved_active_model_scenario_triggers_lockdown_without_creating_file(self) -> None:
        tmp = _workspace_tmp("incident-active-sim")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            scenario = simulate_unapproved_active_model()

        self.assertTrue(scenario["lockdown_triggered"])
        self.assertFalse((tmp / "outputs" / "model_registry" / "active_model.json").exists())

    def test_unapproved_customer_prediction_scenario_triggers_lockdown_without_creating_directory(self) -> None:
        tmp = _workspace_tmp("incident-prediction-sim")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            scenario = simulate_unapproved_customer_predictions()

        self.assertTrue(scenario["lockdown_triggered"])
        self.assertFalse((tmp / "outputs" / "customer_predictions").exists())

    def test_forbidden_action_exposure_triggers_lockdown(self) -> None:
        scenario = simulate_forbidden_action_exposure()

        self.assertTrue(scenario["lockdown_triggered"])
        self.assertEqual(scenario["scenario"], "forbidden_api_action_exposed")

    def test_lockdown_state_disables_training_manual_approval_active_and_prediction(self) -> None:
        state = compute_lockdown_state(
            [
                {"scenario": "stale_evidence_used_for_approval", "lockdown_triggered": True, "lockdown_reason": "stale_evidence_used_for_approval"},
            ]
        )

        self.assertTrue(state["lockdown_triggered"])
        self.assertFalse(state["candidate_training_allowed"])
        self.assertFalse(state["manual_approval_recommended"])
        self.assertFalse(state["active_publish_allowed"])
        self.assertFalse(state["customer_prediction_write_allowed"])

    def test_simulation_report_runs_all_scenarios_and_never_writes_real_forbidden_artifacts(self) -> None:
        tmp = _workspace_tmp("incident-report")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            report = run_incident_drill_simulation(simulation_only=True)

        self.assertIn(report["status"], {"pass", "completed"})
        self.assertEqual(report["scenarios_run"], 8)
        self.assertEqual(report["scenarios_passed"], 8)
        self.assertEqual(report["scenarios_failed"], 0)
        self.assertTrue(report["lockdown_triggered"])
        self.assertTrue(report["simulated_artifacts_only"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertFalse((tmp / "outputs" / "model_registry" / "active_model.json").exists())
        self.assertFalse((tmp / "outputs" / "customer_predictions").exists())
        self.assertIn("rotate managed proxy token", report["remediation_playbook"])
        self.assertIn("require manual review before unlocking", report["remediation_playbook"])
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("Bearer raw", serialized)
        self.assertNotIn("0ad377e", serialized)

    def test_real_lockdown_report_does_not_lock_down_when_no_real_violations_exist(self) -> None:
        tmp = _workspace_tmp("incident-real-clean")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            report = build_incident_drill_report(simulation_only=False)

        self.assertFalse(report["real_lockdown_state"]["lockdown_triggered"])
        self.assertFalse(report["decision_board_override"]["candidate_training_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
