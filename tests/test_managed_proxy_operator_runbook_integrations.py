from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.evidence_bundle_service import write_evidence_bundle
from sn_futures.services.governance_maturity_matrix_service import write_governance_maturity_matrix
from sn_futures.services.research_decision_board_service import build_research_decision_board


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_operator_blocked_but_setup_ready(output: Path) -> None:
    _write_json(
        output / "diagnostics" / "managed_proxy_operator_runbook_report.json",
        {
            "status": "blocked",
            "blocking_reasons": ["env_template_missing"],
            "next_allowed_action": "fix_operator_runbook_templates",
            "endpoint_configured": True,
            "token_configured": True,
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(output / "diagnostics" / "managed_proxy_config_wizard_report.json", {"status": "ready", "blocking_reasons": []})
    _write_json(
        output / "diagnostics" / "managed_proxy_setup_report.json",
        {
            "status": "ready",
            "managed_proxy_health_allowed": True,
            "blocking_reasons": [],
            "next_allowed_action": "run_managed_proxy_health",
        },
    )
    _write_json(output / "diagnostics" / "managed_proxy_health.json", {"status": "ready", "v12_allowed": True, "blocking_reasons": []})
    _write_json(output / "diagnostics" / "managed_proxy_schema_mapping_report.json", {"status": "ready", "schema_mapping_ready": True, "blocking_reasons": []})
    _write_json(output / "diagnostics" / "managed_proxy_reliability_report.json", {"status": "pass", "blocking_reasons": []})
    _write_json(output / "diagnostics" / "managed_data_quality_scorecard.json", {"status": "pass", "gate_passed": True, "blocking_reasons": []})
    _write_json(output / "diagnostics" / "managed_data_audit_manifest.json", {"status": "blocked", "v12_allowed": False, "blocking_reasons": ["pit_audit_missing"]})
    _write_json(output / "diagnostics" / "managed_pit_replay_report.json", {"status": "blocked", "point_in_time_join_ready": False, "blocking_reasons": ["pit_replay_missing"]})
    _write_json(output / "feature_store" / "v12" / "feature_store_manifest.json", {"status": "blocked", "blocking_reasons": ["pit_audit_blocked"]})
    _write_json(output / "training_dataset_manifest_v12.json", {"status": "blocked", "blocking_reasons": ["feature_store_v12_blocked"]})
    _write_json(output / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json", {"status": "blocked", "skipped_reasons": ["training_dataset_v12_blocked"]})
    _write_json(output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json", {"status": "research_only", "manual_approval_recommended": False})
    _write_json(output / "model_research" / "cost_stress_attribution.json", {"status": "fail", "passed": False})
    _write_json(output / "model_research" / "year_concentration_evidence.json", {"status": "pass", "passed": True})
    _write_json(output / "validation" / "cpcv" / "cpcv_report.json", {"status": "blocked"})
    _write_json(output / "model_research" / "model_card.json", {"status": "ready", "active_updated": False, "customer_prediction_generated": False})


class ManagedProxyOperatorRunbookIntegrationsTest(unittest.TestCase):
    def test_decision_board_prioritizes_operator_runbook_template_fix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_operator_blocked_but_setup_ready(output)

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "fix_operator_runbook_templates")
        self.assertFalse(board["candidate_training_allowed"])
        self.assertFalse(board["manual_approval_recommended"])
        self.assertIn("managed_proxy_operator_runbook:env_template_missing", board["blocking_reasons"])

    def test_maturity_matrix_prompt_sequence_prioritizes_operator_runbook_templates_when_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_operator_blocked_but_setup_ready(output)
            build_research_decision_board()

            matrix = write_governance_maturity_matrix()

        self.assertEqual(matrix["recommended_prompt_sequence"][0]["action"], "fix operator runbook templates")
        self.assertIn("operator_runbook", matrix["evidence_paths"])
        self.assertIn("env_template_missing", matrix["critical_gaps"])

    def test_evidence_bundle_indexes_operator_runbook(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_operator_blocked_but_setup_ready(output)

            bundle = write_evidence_bundle()

        self.assertIn("managed_proxy_operator_runbook", bundle["evidence_files"])
        self.assertIn("managed_proxy_operator_runbook", bundle["file_hashes"])


if __name__ == "__main__":
    unittest.main()
