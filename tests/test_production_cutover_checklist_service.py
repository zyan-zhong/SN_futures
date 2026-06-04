from __future__ import annotations

import json
import os
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.production_cutover_checklist_service import (
    build_cutover_report,
    build_noop_release_plan,
    build_production_cutover_checklist,
    validate_cutover_preconditions,
    validate_noop_release_has_no_side_effects,
)


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_ready_cutover_inputs(output: Path) -> None:
    future_expiry = (datetime.now() + timedelta(hours=6)).isoformat(timespec="seconds")
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {
            "status": "ready",
            "generated_at": "2026-06-03T12:00:00",
            "current_research_state": "ready_for_manual_review",
            "next_allowed_action": "manual_review_before_shadow_or_cutover",
            "manual_approval_recommended": True,
            "active_publish_allowed": False,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "model_research" / "manual_approval_report.json",
        {
            "status": "approved_for_shadow_only",
            "generated_at": "2026-06-03T12:00:01",
            "expires_at": future_expiry,
            "two_person_review_pass": True,
            "active_write_allowed": False,
            "customer_prediction_write_allowed": False,
        },
    )
    _write_json(
        output / "model_research" / "shadow_mode_readiness_spec.json",
        {
            "status": "ready",
            "generated_at": "2026-06-03T12:00:02",
            "shadow_mode_allowed": True,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "model_research" / "shadow_output_contract_report.json",
        {
            "status": "ready",
            "generated_at": "2026-06-03T12:00:03",
            "shadow_output_allowed": True,
            "path_isolation_status": "pass",
            "schema_validation_status": "pass",
            "customer_prediction_collision_status": "pass",
        },
    )
    _write_json(
        output / "model_research" / "model_registry_safety_report.json",
        {
            "status": "ready",
            "generated_at": "2026-06-03T12:00:04",
            "active_write_allowed": False,
            "rollback_target_available": True,
            "unapproved_active_detected": False,
            "rollback_plan": {"status": "ready", "rollback_target_available": True},
        },
    )
    _write_json(
        output / "model_research" / "incident_drill_report.json",
        {
            "status": "pass",
            "generated_at": "2026-06-03T12:00:05",
            "scenarios_passed": 8,
            "scenarios_failed": 0,
            "real_lockdown_state": {"lockdown_triggered": False, "lockdown_reasons": []},
        },
    )
    _write_json(
        output / "model_research" / "governance_observability_report.json",
        {
            "status": "pass",
            "generated_at": "2026-06-03T12:00:06",
            "slo_results": {"status": "pass"},
            "telemetry_summary": {"secret_scan_status": "pass"},
        },
    )
    _write_json(
        output / "model_research" / "evidence_freshness_report.json",
        {
            "status": "pass",
            "generated_at": "2026-06-03T12:00:07",
            "stale_reports": [],
            "missing_timestamps": [],
            "timestamp_inversions": [],
        },
    )
    _write_json(
        output / "governance" / "external_audit_export" / "audit_index.json",
        {
            "status": "ready",
            "generated_at": "2026-06-03T12:00:08",
            "redaction_status": "pass",
            "missing_reports": [],
            "incomplete_reports": [],
        },
    )
    _write_json(
        output / "model_research" / "post_release_monitoring_spec_report.json",
        {
            "status": "ready",
            "generated_at": "2026-06-03T12:00:09",
            "monitoring_mode": "planning_only",
            "live_monitoring_enabled": True,
            "sentinel_count": 16,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )


class ProductionCutoverChecklistServiceTest(unittest.TestCase):
    def test_current_blocked_state_does_not_allow_cutover(self) -> None:
        tmp = _workspace_tmp("cutover-current-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            report = build_cutover_report()

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["cutover_allowed"])
        self.assertIn("decision_board_not_ready_for_manual_review", report["blocking_reasons"])
        self.assertFalse(report["active_publish_allowed"])
        self.assertFalse(report["customer_prediction_write_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_ready_inputs_still_keep_active_and_prediction_writes_disabled(self) -> None:
        tmp = _workspace_tmp("cutover-ready-inputs")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_ready_cutover_inputs(output)
            checklist = build_production_cutover_checklist()
            preconditions = validate_cutover_preconditions(checklist["evidence"])

        self.assertEqual(preconditions["status"], "pass")
        self.assertTrue(preconditions["cutover_allowed"])
        self.assertFalse(checklist["active_publish_allowed"])
        self.assertFalse(checklist["customer_prediction_write_allowed"])

    def test_manual_approval_missing_blocks_cutover(self) -> None:
        tmp = _workspace_tmp("cutover-manual-missing")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_ready_cutover_inputs(output)
            (output / "model_research" / "manual_approval_report.json").unlink()
            report = build_cutover_report()

        self.assertFalse(report["cutover_allowed"])
        self.assertIn("manual_approval_missing_or_expired", report["blocking_reasons"])

    def test_individual_gate_failures_block_cutover(self) -> None:
        cases = [
            ("shadow_mode_readiness_spec.json", {"shadow_mode_allowed": False}, "shadow_mode_readiness_not_pass"),
            ("shadow_output_contract_report.json", {"status": "blocked"}, "shadow_output_contract_not_pass"),
            ("model_registry_safety_report.json", {"status": "violation"}, "registry_safety_not_pass"),
            ("incident_drill_report.json", {"status": "fail"}, "incident_drill_not_pass"),
            ("evidence_freshness_report.json", {"status": "blocked", "stale_reports": ["decision_board"]}, "evidence_freshness_not_pass"),
            ("post_release_monitoring_spec_report.json", {"status": "blocked", "live_monitoring_enabled": False}, "post_release_monitoring_spec_not_ready"),
            ("model_registry_safety_report.json", {"rollback_target_available": False}, "rollback_target_missing"),
        ]
        for filename, override, reason in cases:
            with self.subTest(reason=reason):
                tmp = _workspace_tmp(f"cutover-{reason}")
                with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
                    output = Path(tmp) / "outputs"
                    _seed_ready_cutover_inputs(output)
                    path = output / "model_research" / filename
                    payload = json.loads(path.read_text(encoding="utf-8"))
                    payload.update(override)
                    _write_json(path, payload)
                    report = build_cutover_report()

                self.assertFalse(report["cutover_allowed"])
                self.assertIn(reason, report["blocking_reasons"])

    def test_noop_release_plan_has_no_side_effects_or_customer_outputs(self) -> None:
        tmp = _workspace_tmp("cutover-noop")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            plan = build_noop_release_plan(intended_candidate_version="v12")
            side_effects = validate_noop_release_has_no_side_effects(plan)
            ledger = output / "model_research" / "run_ledger" / "research_run_ledger.jsonl"
            ledger_text = ledger.read_text(encoding="utf-8")

        self.assertEqual(plan["release_type"], "noop")
        self.assertTrue(plan["noop_release_plan_ready"])
        self.assertEqual(side_effects["status"], "pass")
        self.assertIn("production_noop_release_plan", ledger_text)
        self.assertIn('"run_type": "safe_dry_run"', ledger_text)
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "customer_predictions").exists())
        self.assertFalse(plan["training_invoked"])
        self.assertFalse(plan["active_updated"])
        self.assertFalse(plan["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
