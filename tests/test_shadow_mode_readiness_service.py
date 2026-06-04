from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.shadow_mode_readiness_service import (  # noqa: E402
    build_shadow_mode_readiness_spec,
    build_shadow_output_contract,
    validate_prediction_isolation,
    validate_shadow_mode_entry_gates,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_passing_evidence(output: Path, *, manual_approval: bool = True, freshness_status: str = "ready") -> None:
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {
            "status": "ready" if manual_approval else "blocked",
            "manual_approval_recommended": manual_approval,
            "active_publish_allowed": False,
            "candidate_training_allowed": False,
            "candidate_v12_allowed": False,
            "blocking_reasons": [] if manual_approval else ["manual_approval_missing"],
        },
    )
    _write_json(
        output / "model_research" / "evidence_freshness_report.json",
        {
            "status": freshness_status,
            "stale_reports": [] if freshness_status == "ready" else ["candidate_v10_report"],
            "missing_timestamps": [],
            "timestamp_inversions": [],
            "blocking_reasons": [] if freshness_status == "ready" else ["stale_reports_present"],
        },
    )
    _write_json(
        output / "model_research" / "evidence_bundle_index.json",
        {
            "status": "ready",
            "missing_reports": [],
            "incomplete_reports": [],
            "no_active_confirmation": {"confirmed": True},
            "no_prediction_confirmation": {"confirmed": True},
        },
    )
    _write_json(
        output / "diagnostics" / "managed_data_audit_manifest.json",
        {
            "status": "ready",
            "v12_allowed": True,
            "leakage_checks": {"point_in_time_join_ready": True},
            "blocking_reasons": [],
        },
    )
    _write_json(
        output / "diagnostics" / "managed_data_quality_scorecard.json",
        {
            "status": "ready",
            "gate_passed": True,
            "blocking_reasons": [],
        },
    )
    _write_json(
        output / "validation" / "cpcv" / "cpcv_report.json",
        {
            "status": "pass",
            "pbo": {"pbo": 0.1, "passed": True},
            "reality_check": {"aggregate_p_value": 0.01, "passed": True},
        },
    )
    _write_json(
        output / "model_research" / "cost_stress_attribution.json",
        {
            "status": "pass",
            "candidate_v10": {
                "cost_stress_attribution": {
                    "status": "pass",
                    "passed": True,
                    "failure_drivers": [],
                }
            },
        },
    )
    _write_json(
        output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json",
        {
            "status": "success",
            "candidate_version": "v10",
            "manual_approval_recommended": manual_approval,
            "v10_gate_checks": {"pbo_lt_0_2": True, "reality_check_pass": True},
            "cost_stress_attribution": {"status": "pass", "passed": True, "failure_drivers": []},
        },
    )


class ShadowModeReadinessServiceTest(unittest.TestCase):
    def test_current_blocked_state_disallows_shadow_mode_and_keeps_prediction_outputs_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "model_research" / "research_decision_board.json",
                {
                    "status": "blocked",
                    "manual_approval_recommended": False,
                    "active_publish_allowed": False,
                    "blocking_reasons": ["managed_data_blocked"],
                },
            )

            result = build_shadow_mode_readiness_spec()

            self.assertFalse((output / "customer_predictions").exists())
            self.assertFalse((output / "model_registry" / "active_model.json").exists())

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["shadow_mode_allowed"])
        self.assertIn("manual_approval_missing", result["blocked_gates"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_shadow_output_contract_is_separate_from_customer_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            contract = build_shadow_output_contract()
            isolation = validate_prediction_isolation(contract)

        self.assertTrue(contract["paths_are_separate"])
        self.assertNotEqual(contract["shadow_output_root"], contract["customer_predictions_root"])
        self.assertTrue(isolation["customer_predictions_absent"])
        self.assertEqual(isolation["status"], "pass")

    def test_missing_manual_approval_blocks_even_when_other_evidence_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_passing_evidence(output, manual_approval=False)

            result = build_shadow_mode_readiness_spec()

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["shadow_mode_allowed"])
        self.assertIn("manual_approval_missing", result["blocked_gates"])

    def test_stale_evidence_blocks_shadow_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_passing_evidence(output, manual_approval=True, freshness_status="blocked")

            result = build_shadow_mode_readiness_spec()

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["shadow_mode_allowed"])
        self.assertIn("stale_evidence_present", result["blocked_gates"])

    def test_customer_predictions_directory_blocks_prediction_isolation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_passing_evidence(output)
            (output / "customer_predictions").mkdir(parents=True)

            result = build_shadow_mode_readiness_spec()

        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["shadow_mode_allowed"])
        self.assertIn("customer_predictions_present", result["blocked_gates"])

    def test_entry_gate_helper_allows_shadow_only_for_passing_evidence_and_locked_active_publish(self) -> None:
        gates = validate_shadow_mode_entry_gates(
            decision_board={"manual_approval_recommended": True, "active_publish_allowed": False},
            evidence_freshness={"status": "ready", "stale_reports": [], "missing_timestamps": [], "timestamp_inversions": []},
            cost_attribution={"status": "pass", "passed": True},
            cpcv_report={"status": "pass", "pbo": {"passed": True}, "reality_check": {"passed": True}},
            pit_audit={"status": "ready", "leakage_checks": {"point_in_time_join_ready": True}},
            data_quality={"status": "ready", "gate_passed": True},
        )

        self.assertEqual(gates["status"], "pass")
        self.assertEqual(gates["blocked_gates"], [])
        self.assertTrue(all(item["passed"] for item in gates["entry_gates"]))


if __name__ == "__main__":
    unittest.main()
