from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.research_decision_board_service import build_research_decision_board


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class ResearchDecisionBoardServiceTest(unittest.TestCase):
    def test_managed_proxy_blocked_prevents_candidate_training_and_active_publish(self) -> None:
        tmp = _workspace_tmp("decision-board-managed-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "diagnostics" / "managed_proxy_health.json",
                {
                    "status": "blocked",
                    "provider_status": "disabled",
                    "v12_allowed": False,
                    "blocking_reasons": ["managed_proxy_disabled"],
                    "next_allowed_action": "configure_managed_proxy_endpoint_and_token",
                    "token_masked": "tu***en",
                },
            )
            _write_json(
                output / "diagnostics" / "managed_data_audit_manifest.json",
                {"status": "blocked", "blocking_reasons": ["managed_audit_blocked"], "v12_allowed": False},
            )

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertIn(board["next_allowed_action"], {"configure_managed_proxy_endpoint_and_token", "no_action_until_data_ready"})
        self.assertFalse(board["candidate_training_allowed"])
        self.assertFalse(board["candidate_v12_allowed"])
        self.assertFalse(board["manual_approval_recommended"])
        self.assertFalse(board["active_publish_allowed"])
        self.assertIn("managed_proxy_disabled", board["blocking_reasons"])
        self.assertIn("managed_proxy_disabled", board["top_blocking_reasons"])
        self.assertTrue(board["manifest_path"].endswith("research_decision_board.json"))
        self.assertFalse(board["training_invoked"])
        self.assertFalse(board["active_updated"])
        self.assertFalse(board["customer_prediction_generated"])

    def test_candidate_v10_cost_fail_overrides_year_pass_and_blocks_manual_approval(self) -> None:
        tmp = _workspace_tmp("decision-board-cost-fail")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "diagnostics" / "managed_proxy_config_wizard_report.json",
                {
                    "status": "ready",
                    "next_allowed_action": "run_managed_proxy_setup_dry_run",
                    "blocking_reasons": [],
                    "endpoint_configured": True,
                    "token_configured": True,
                },
            )
            _write_json(
                output / "diagnostics" / "managed_proxy_setup_report.json",
                {
                    "status": "ready",
                    "next_allowed_action": "run_managed_proxy_health",
                    "blocking_reasons": [],
                    "managed_proxy_health_allowed": True,
                    "pit_audit_allowed": True,
                    "feature_store_v12_allowed": False,
                },
            )
            _write_json(
                output / "diagnostics" / "managed_proxy_health.json",
                {"status": "ready", "provider_status": "success_with_required_fields", "v12_allowed": True, "blocking_reasons": []},
            )
            _write_json(
                output / "diagnostics" / "managed_data_audit_manifest.json",
                {"status": "ready", "v12_allowed": True, "blocking_reasons": [], "leakage_checks": {"point_in_time_join_ready": True}},
            )
            _write_json(
                output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json",
                {
                    "status": "success",
                    "candidate_version": "v10",
                    "manual_approval_recommended": True,
                    "v10_gate_checks": {"pbo_lt_0_2": True, "reality_check_pass": True},
                    "year_concentration_evidence": {"status": "pass", "passed": True},
                    "cost_stress_attribution": {
                        "status": "fail",
                        "passed": False,
                        "failure_drivers": ["institutional_3x_cost_negative"],
                        "by_horizon": {"rows": [{"horizon": "1d", "net_expectancy_3x": -0.1}]},
                        "by_regime": {"rows": [{"regime_label": "range", "net_expectancy_3x": -0.05}]},
                        "by_year": {"rows": [{"year": 2022, "net_expectancy_3x": -0.2}]},
                    },
                },
            )

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "candidate_trained_gate_failed")
        self.assertEqual(board["next_allowed_action"], "fix_candidate_v10_cost_failure")
        self.assertFalse(board["manual_approval_recommended"])
        self.assertFalse(board["active_publish_allowed"])
        self.assertEqual(board["candidate_v10_summary"]["year_evidence_status"], "pass")
        self.assertEqual(board["candidate_v10_summary"]["cost_attribution_status"], "fail")
        self.assertIn("institutional_3x_cost_negative", board["candidate_v10_summary"]["main_cost_failure_drivers"])
        self.assertIn("cost_attribution:institutional_3x_cost_negative", board["blocking_reasons"])

    def test_missing_manifest_is_not_treated_as_pass(self) -> None:
        tmp = _workspace_tmp("decision-board-missing")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            board = build_research_decision_board()

        self.assertFalse(board["candidate_training_allowed"])
        self.assertFalse(board["candidate_v12_allowed"])
        self.assertFalse(board["manual_approval_recommended"])
        self.assertIn("managed_proxy_health:missing", board["stale_or_missing_reports"])
        self.assertIn("candidate_v10_report:missing", board["stale_or_missing_reports"])

    def test_managed_proxy_setup_refines_next_allowed_action(self) -> None:
        tmp = _workspace_tmp("decision-board-setup")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "diagnostics" / "managed_proxy_setup_report.json",
                {
                    "status": "blocked",
                    "next_allowed_action": "configure_managed_proxy_token",
                    "blocking_reasons": ["managed_proxy_token_missing"],
                    "managed_proxy_health_allowed": False,
                    "pit_audit_allowed": False,
                    "feature_store_v12_allowed": False,
                },
            )
            _write_json(
                output / "diagnostics" / "managed_proxy_health.json",
                {
                    "status": "blocked",
                    "provider_status": "token_missing",
                    "v12_allowed": False,
                    "blocking_reasons": ["managed_proxy_token_missing"],
                    "next_allowed_action": "configure_managed_proxy_endpoint_and_token",
                },
            )
            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "configure_managed_proxy_token")
        self.assertIn("managed_proxy_setup:managed_proxy_token_missing", board["blocking_reasons"])
        self.assertIn("managed_proxy_setup", board["evidence_paths"])

    def test_config_wizard_incomplete_templates_take_priority_over_setup(self) -> None:
        tmp = _workspace_tmp("decision-board-wizard-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "diagnostics" / "managed_proxy_config_wizard_report.json",
                {
                    "status": "blocked",
                    "next_allowed_action": "fix_managed_proxy_config_templates",
                    "blocking_reasons": ["env_template_missing"],
                    "endpoint_configured": False,
                    "token_configured": False,
                },
            )
            _write_json(
                output / "diagnostics" / "managed_proxy_setup_report.json",
                {
                    "status": "blocked",
                    "next_allowed_action": "configure_managed_proxy_token",
                    "blocking_reasons": ["managed_proxy_token_missing"],
                    "managed_proxy_health_allowed": False,
                },
            )
            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "fix_managed_proxy_config_templates")
        self.assertIn("managed_proxy_config_wizard:env_template_missing", board["blocking_reasons"])

    def test_complete_wizard_with_missing_endpoint_or_token_guides_safe_configuration(self) -> None:
        tmp = _workspace_tmp("decision-board-wizard-ready")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "diagnostics" / "managed_proxy_config_wizard_report.json",
                {
                    "status": "ready",
                    "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
                    "blocking_reasons": [],
                    "endpoint_configured": False,
                    "token_configured": False,
                },
            )
            _write_json(
                output / "diagnostics" / "managed_proxy_setup_report.json",
                {
                    "status": "blocked",
                    "next_allowed_action": "enable_managed_proxy",
                    "blocking_reasons": ["managed_proxy_disabled"],
                    "managed_proxy_health_allowed": False,
                },
            )
            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "configure_managed_proxy_endpoint_or_token")

    def test_schema_mapping_failure_guides_mapping_fix_without_training(self) -> None:
        tmp = _workspace_tmp("decision-board-schema")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "diagnostics" / "managed_proxy_config_wizard_report.json",
                {
                    "status": "ready",
                    "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
                    "blocking_reasons": [],
                    "endpoint_configured": True,
                    "token_configured": True,
                },
            )
            _write_json(
                output / "diagnostics" / "managed_proxy_setup_report.json",
                {
                    "status": "ready",
                    "next_allowed_action": "run_managed_proxy_health",
                    "blocking_reasons": [],
                    "managed_proxy_health_allowed": True,
                },
            )
            _write_json(
                output / "diagnostics" / "managed_proxy_schema_mapping_report.json",
                {
                    "status": "blocked",
                    "schema_mapping_ready": False,
                    "blocking_reasons": ["canonical_timestamp_fields_missing"],
                    "training_invoked": False,
                    "active_updated": False,
                    "customer_prediction_generated": False,
                },
            )
            _write_json(
                output / "diagnostics" / "managed_proxy_health.json",
                {"status": "ready", "provider_status": "success_with_required_fields", "v12_allowed": True, "blocking_reasons": []},
            )
            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "fix_managed_proxy_schema_mapping")
        self.assertFalse(board["candidate_training_allowed"])
        self.assertIn("managed_proxy_schema_mapping:canonical_timestamp_fields_missing", board["blocking_reasons"])
        self.assertFalse(board["training_invoked"])
        self.assertFalse(board["active_updated"])
        self.assertFalse(board["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
