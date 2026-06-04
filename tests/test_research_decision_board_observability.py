from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.research_decision_board_service import build_research_decision_board  # noqa: E402


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


def _write_ready_chain(output: Path) -> None:
    _write_json(output / "diagnostics" / "managed_proxy_config_wizard_report.json", {"status": "ready", "generated_at": "2026-06-03T12:00:00", "next_allowed_action": "run_managed_proxy_setup_dry_run"})
    _write_json(output / "diagnostics" / "managed_proxy_setup_report.json", {"status": "ready", "generated_at": "2026-06-03T12:00:00", "managed_proxy_health_allowed": True, "blocking_reasons": []})
    _write_json(output / "diagnostics" / "managed_proxy_schema_mapping_report.json", {"status": "pass", "generated_at": "2026-06-03T12:00:00", "schema_mapping_ready": True, "blocking_reasons": []})
    _write_json(output / "diagnostics" / "managed_proxy_health.json", {"status": "ready", "generated_at": "2026-06-03T12:00:00", "v12_allowed": True, "blocking_reasons": []})
    _write_json(output / "diagnostics" / "managed_proxy_reliability_report.json", {"status": "pass", "generated_at": "2026-06-03T12:00:00", "blocking_reasons": []})
    _write_json(output / "diagnostics" / "managed_data_quality_scorecard.json", {"status": "pass", "generated_at": "2026-06-03T12:00:00", "gate_passed": True, "blocking_reasons": []})
    _write_json(output / "diagnostics" / "managed_data_audit_manifest.json", {"status": "ready", "generated_at": "2026-06-03T12:00:00", "v12_allowed": True, "blocking_reasons": [], "leakage_checks": {"point_in_time_join_ready": True}})
    _write_json(output / "feature_store" / "v12" / "feature_store_manifest.json", {"status": "ready", "generated_at": "2026-06-03T12:00:00", "no_lookahead_pass": True, "point_in_time_join_ready": True})
    _write_json(output / "training_dataset_manifest_v12.json", {"status": "ready", "generated_at": "2026-06-03T12:00:00", "leakage_check_pass": True})
    _write_json(output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json", {"status": "success", "generated_at": "2026-06-03T12:00:00", "manual_approval_recommended": True, "v10_gate_checks": {"pbo_lt_0_2": True, "reality_check_pass": True}, "year_concentration_evidence": {"status": "pass", "passed": True}, "cost_stress_attribution": {"status": "pass", "passed": True, "failure_drivers": []}})
    _write_json(output / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json", {"status": "success", "generated_at": "2026-06-03T12:00:00", "manual_approval_recommended": True, "blocking_reasons": []})
    _write_json(output / "model_research" / "year_concentration_evidence.json", {"status": "pass", "generated_at": "2026-06-03T12:00:00", "passed": True})
    _write_json(output / "model_research" / "cost_stress_attribution.json", {"status": "pass", "generated_at": "2026-06-03T12:00:00", "passed": True, "failure_drivers": []})
    _write_json(output / "validation" / "cpcv" / "cpcv_report.json", {"status": "pass", "generated_at": "2026-06-03T12:00:00"})
    _write_json(output / "model_research" / "evidence_freshness_report.json", {"status": "pass", "generated_at": "2026-06-03T12:00:00", "stale_reports": [], "missing_timestamps": [], "timestamp_inversions": [], "blocking_reasons": []})


class ResearchDecisionBoardObservabilityTest(unittest.TestCase):
    def test_observability_fail_blocks_manual_approval_and_sets_secret_scan_next_action(self) -> None:
        tmp = _workspace_tmp("board-observability-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_ready_chain(output)
            _write_json(
                output / "model_research" / "governance_observability_report.json",
                {
                    "status": "blocked",
                    "generated_at": "2026-06-03T12:00:00",
                    "slo_results": {"secret_scan_pass": {"status": "fail"}},
                    "telemetry_summary": {"secret_scan_status": "fail"},
                    "blocking_reasons": ["secret_scan_failed"],
                    "training_invoked": False,
                    "active_updated": False,
                    "customer_prediction_generated": False,
                },
            )

            board = build_research_decision_board()

        self.assertFalse(board["manual_approval_recommended"])
        self.assertFalse(board["active_publish_allowed"])
        self.assertEqual(board["governance_observability_summary"]["status"], "blocked")
        self.assertIn("governance_observability:secret_scan_failed", board["blocking_reasons"])
        self.assertEqual(board["next_allowed_action"], "fix_secret_scan_violation")
        self.assertFalse(board["training_invoked"])
        self.assertFalse(board["active_updated"])
        self.assertFalse(board["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
