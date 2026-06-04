from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.governance_maturity_matrix_service import (
    build_final_hardening_roadmap,
    build_recommended_prompt_sequence,
    get_latest_governance_maturity_matrix,
    identify_hardening_gaps,
    score_governance_domain,
    write_governance_maturity_matrix,
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


def _seed_governance_evidence(output: Path) -> None:
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {
            "status": "blocked",
            "current_research_state": "managed_data_blocked",
            "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
            "manual_approval_recommended": False,
            "active_publish_allowed": False,
            "blocking_reasons": ["managed_proxy_disabled", "cost_attribution:year_specific_cost_drag"],
            "top_blocking_reasons": ["managed_proxy_disabled", "cost_attribution:year_specific_cost_drag"],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(output / "diagnostics" / "managed_proxy_config_wizard_report.json", {"status": "ready", "blocking_reasons": []})
    _write_json(
        output / "diagnostics" / "managed_proxy_setup_report.json",
        {
            "status": "blocked",
            "endpoint_configured": False,
            "token_configured": False,
            "blocking_reasons": ["managed_proxy_disabled"],
            "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
        },
    )
    _write_json(
        output / "diagnostics" / "managed_proxy_schema_mapping_report.json",
        {"status": "blocked", "schema_mapping_ready": False, "blocking_reasons": ["canonical_timestamp_fields_missing"]},
    )
    _write_json(
        output / "diagnostics" / "managed_pit_replay_report.json",
        {"status": "blocked", "point_in_time_join_ready": False, "blocking_reasons": ["point_in_time_join_not_ready"]},
    )
    _write_json(
        output / "diagnostics" / "managed_data_audit_manifest.json",
        {"status": "blocked", "v12_allowed": False, "blocking_reasons": ["managed_fundamental_fields_missing"]},
    )
    _write_json(
        output / "diagnostics" / "managed_data_quality_scorecard.json",
        {"status": "blocked", "gate_passed": False, "blocking_reasons": ["managed_rows_missing"]},
    )
    _write_json(output / "diagnostics" / "managed_proxy_reliability_report.json", {"status": "blocked", "blocking_reasons": ["managed_proxy_disabled"]})
    _write_json(output / "feature_store" / "v12" / "feature_store_manifest.json", {"status": "blocked", "blocking_reasons": ["managed_data_blocked"]})
    _write_json(output / "training_dataset_manifest_v12.json", {"status": "blocked", "blocking_reasons": ["feature_store_v12_blocked"]})
    _write_json(
        output / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json",
        {"status": "blocked", "skipped_reasons": ["training_dataset_v12_blocked"], "manual_approval_recommended": False},
    )
    _write_json(
        output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json",
        {
            "status": "research_only",
            "candidate_version": "v10",
            "manual_approval_recommended": False,
            "year_concentration_evidence": {"status": "pass", "passed": True},
            "cost_stress_attribution": {
                "status": "fail",
                "passed": False,
                "failure_drivers": ["institutional_2x_cost_negative", "year_specific_cost_drag"],
            },
        },
    )
    _write_json(output / "model_research" / "cost_stress_attribution.json", {"status": "fail", "passed": False, "failure_drivers": ["year_specific_cost_drag"]})
    _write_json(output / "model_research" / "year_concentration_evidence.json", {"status": "pass", "passed": True})
    _write_json(output / "validation" / "cpcv" / "cpcv_report.json", {"status": "blocked", "pbo": {"pbo": 0.6}, "reality_check": {"passed": False}})
    _write_json(output / "model_research" / "evidence_freshness_report.json", {"status": "ready", "stale_reports": [], "blocking_reasons": []})
    _write_json(output / "model_research" / "evidence_bundle_index.json", {"status": "ready", "missing_reports": [], "incomplete_reports": []})
    _write_json(output / "governance" / "external_audit_export" / "audit_index.json", {"status": "ready", "missing_reports": [], "incomplete_reports": []})
    _write_json(output / "model_research" / "governance_access_control_report.json", {"status": "guarded", "forbidden_actions": ["active_write", "customer_prediction_write"]})
    _write_json(output / "model_research" / "governance_observability_report.json", {"status": "pass", "slo_results": {"status": "pass"}, "blocking_reasons": []})
    _write_json(output / "model_research" / "incident_drill_report.json", {"status": "pass", "scenarios_passed": 8, "scenarios_failed": 0})
    _write_json(output / "model_research" / "manual_approval_report.json", {"status": "blocked_by_gates", "approval_request_allowed": False})
    _write_json(output / "model_research" / "shadow_mode_readiness_report.json", {"status": "blocked", "shadow_mode_allowed": False, "blocked_gates": ["manual_approval_missing"]})
    _write_json(output / "model_research" / "shadow_output_contract_report.json", {"status": "ready", "shadow_output_allowed": False})
    _write_json(output / "model_research" / "shadow_replay_report.json", {"status": "research_only", "customer_prediction_generated": False})
    _write_json(output / "model_research" / "post_release_monitoring_spec_report.json", {"status": "planning_only", "monitoring_mode": "planning_only", "live_monitoring_enabled": False})
    _write_json(output / "model_research" / "rollback_rehearsal_report.json", {"status": "ready", "quarantine_needed": False})
    _write_json(output / "model_research" / "model_registry_safety_report.json", {"status": "blocked", "active_write_allowed": False, "rollback_target_available": False})
    _write_json(output / "model_research" / "production_cutover_checklist_report.json", {"status": "blocked", "cutover_allowed": False})
    _write_json(
        output / "model_research" / "model_card.json",
        {
            "status": "ready",
            "current_status": "managed_data_blocked / research_only",
            "gate_failures": ["managed_proxy_disabled", "cost_attribution:year_specific_cost_drag"],
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(output / "model_research" / "run_ledger" / "research_run_ledger_report.json", {"status": "ready", "violation_count": 0})


class GovernanceMaturityMatrixServiceTest(unittest.TestCase):
    def test_missing_critical_report_marks_matrix_incomplete_without_side_effects(self) -> None:
        tmp = _workspace_tmp("maturity-missing")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            matrix = write_governance_maturity_matrix()

        self.assertEqual(matrix["status"], "incomplete")
        self.assertIn("research_decision_board", matrix["missing_controls"])
        self.assertFalse(matrix["production_readiness"])
        self.assertFalse(matrix["training_invoked"])
        self.assertFalse(matrix["active_updated"])
        self.assertFalse(matrix["customer_prediction_generated"])

    def test_blocked_data_chain_scores_low_while_governance_controls_score_higher(self) -> None:
        tmp = _workspace_tmp("maturity-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_governance_evidence(output)
            matrix = write_governance_maturity_matrix()
            latest = get_latest_governance_maturity_matrix()

        scores = matrix["domain_scores"]
        self.assertEqual(matrix["current_research_state"], "managed_data_blocked")
        self.assertFalse(matrix["production_readiness"])
        self.assertLessEqual(scores["Managed Proxy Configuration"]["score"], 0.25)
        self.assertLessEqual(scores["Schema Mapping"]["score"], 0.25)
        self.assertLessEqual(scores["PIT / No-Lookahead"]["score"], 0.25)
        self.assertLessEqual(scores["Managed Data Quality"]["score"], 0.25)
        self.assertLessEqual(scores["Feature Store v12"]["score"], 0.25)
        self.assertLessEqual(scores["Training Dataset v12"]["score"], 0.25)
        self.assertLessEqual(scores["Candidate v12"]["score"], 0.25)
        self.assertLessEqual(scores["Cost Robustness"]["score"], 0.25)
        self.assertGreater(scores["Year Evidence"]["score"], scores["Cost Robustness"]["score"])
        self.assertGreaterEqual(scores["Observability / SLO"]["score"], 0.75)
        self.assertGreaterEqual(scores["Incident Response"]["score"], 0.75)
        self.assertGreaterEqual(scores["Rollback / Quarantine"]["score"], 0.75)
        self.assertGreaterEqual(scores["Model Card / Risk Disclosure"]["score"], 0.75)
        self.assertLessEqual(scores["Production Cutover"]["score"], 0.25)
        self.assertEqual(latest["report_path"], matrix["report_path"])

    def test_matrix_does_not_treat_planning_research_or_rehearsal_as_production_ready(self) -> None:
        tmp = _workspace_tmp("maturity-not-production")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_governance_evidence(output)
            matrix = write_governance_maturity_matrix()

        statuses = matrix["domain_statuses"]
        self.assertEqual(statuses["Shadow Replay"], "research_only")
        self.assertEqual(statuses["Post-Release Monitoring Spec"], "planning_only")
        self.assertEqual(statuses["Rollback / Quarantine"], "pass")
        self.assertFalse(matrix["production_readiness"])
        self.assertFalse(matrix["shadow_readiness"]["ready"])

    def test_recommended_prompt_sequence_starts_with_managed_proxy_onboarding(self) -> None:
        tmp = _workspace_tmp("maturity-sequence")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_governance_evidence(output)
            matrix = write_governance_maturity_matrix()

        sequence = matrix["recommended_prompt_sequence"]
        self.assertEqual(sequence[0]["action"], "configure managed proxy endpoint/token")
        self.assertIn("rerun managed proxy setup/health", [item["action"] for item in sequence])
        self.assertIn("build Feature Store v12 only if all upstream ready", [item["action"] for item in sequence])
        self.assertIn("only then revisit manual approval / shadow mode", [item["action"] for item in sequence])
        self.assertEqual(matrix["next_allowed_action"], "configure_managed_proxy_endpoint_or_token")

    def test_roadmap_groups_immediate_data_v12_candidate_and_cutover_blockers(self) -> None:
        tmp = _workspace_tmp("maturity-roadmap")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_governance_evidence(output)
            matrix = write_governance_maturity_matrix()

        roadmap = matrix["roadmap"]
        self.assertIn("immediate blockers", roadmap)
        self.assertIn("data onboarding blockers", roadmap)
        self.assertIn("PIT/schema/data quality blockers", roadmap)
        self.assertIn("v12 build blockers", roadmap)
        self.assertIn("candidate research blockers", roadmap)
        self.assertIn("v10 cost robustness blockers", roadmap)
        self.assertIn("shadow readiness blockers", roadmap)
        self.assertIn("production cutover blockers", roadmap)
        self.assertGreater(len(matrix["critical_gaps"]), 0)
        self.assertGreater(len(matrix["completed_controls"]), 0)
        self.assertIn("missing_controls", matrix)

    def test_public_helpers_score_and_gap_summary(self) -> None:
        report = {"status": "blocked", "blocking_reasons": ["managed_proxy_disabled"], "path": "x.json"}

        scored = score_governance_domain("Managed Proxy Configuration", report)
        gaps = identify_hardening_gaps({"Managed Proxy Configuration": scored})
        roadmap = build_final_hardening_roadmap(gaps)
        sequence = build_recommended_prompt_sequence({"current_research_state": "managed_data_blocked"})

        self.assertEqual(scored["status"], "blocked")
        self.assertLess(scored["score"], 0.5)
        self.assertIn("managed_proxy_disabled", gaps["critical_gaps"])
        self.assertIn("immediate blockers", roadmap)
        self.assertEqual(sequence[0]["action"], "configure managed proxy endpoint/token")


if __name__ == "__main__":
    unittest.main()
