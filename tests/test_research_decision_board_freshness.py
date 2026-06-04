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

from sn_futures.services.research_decision_board_service import build_research_decision_board


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"
BASE_TIME = datetime(2026, 6, 3, 12, 0, 0)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _ts(hours_delta: int = 0) -> str:
    return (BASE_TIME + timedelta(hours=hours_delta)).isoformat(timespec="seconds")


class ResearchDecisionBoardFreshnessTest(unittest.TestCase):
    def test_freshness_fail_blocks_manual_approval_and_candidate_v12(self) -> None:
        tmp = _workspace_tmp("board-freshness-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "diagnostics" / "managed_proxy_config_wizard_report.json",
                {"status": "ready", "generated_at": _ts(0), "blocking_reasons": [], "next_allowed_action": "run_managed_proxy_setup_dry_run"},
            )
            _write_json(
                output / "diagnostics" / "managed_proxy_setup_report.json",
                {"status": "ready", "generated_at": _ts(0), "blocking_reasons": [], "managed_proxy_health_allowed": True},
            )
            _write_json(
                output / "diagnostics" / "managed_proxy_health.json",
                {"status": "ready", "generated_at": _ts(0), "v12_allowed": True, "provider_status": "success_with_required_fields", "blocking_reasons": []},
            )
            _write_json(
                output / "diagnostics" / "managed_data_audit_manifest.json",
                {"status": "ready", "generated_at": _ts(0), "v12_allowed": True, "blocking_reasons": [], "leakage_checks": {"point_in_time_join_ready": True}},
            )
            _write_json(
                output / "feature_store" / "v12" / "feature_store_manifest.json",
                {"status": "ready", "generated_at": _ts(1), "no_lookahead_pass": True, "point_in_time_join_ready": True, "feature_store_version": "v12"},
            )
            _write_json(
                output / "training_dataset_manifest_v12.json",
                {"status": "ready", "generated_at": _ts(2), "leakage_check_pass": True, "dataset_version": "v12"},
            )
            _write_json(
                output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json",
                {
                    "status": "success",
                    "generated_at": _ts(3),
                    "manual_approval_recommended": True,
                    "v10_gate_checks": {"pbo_lt_0_2": True, "reality_check_pass": True},
                    "year_concentration_evidence": {"status": "pass", "passed": True},
                    "cost_stress_attribution": {"status": "pass", "passed": True, "failure_drivers": []},
                },
            )
            _write_json(
                output / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json",
                {"status": "success", "generated_at": _ts(3), "manual_approval_recommended": True, "dataset_version": "v12", "blocking_reasons": []},
            )
            _write_json(
                output / "model_research" / "evidence_freshness_report.json",
                {
                    "status": "blocked",
                    "generated_at": _ts(4),
                    "stale_reports": ["candidate_v12_report"],
                    "missing_timestamps": [],
                    "timestamp_inversions": [],
                    "blocking_reasons": ["freshness:candidate_v12_report_stale"],
                    "training_invoked": False,
                    "active_updated": False,
                    "customer_prediction_generated": False,
                },
            )

            board = build_research_decision_board()

        self.assertFalse(board["manual_approval_recommended"])
        self.assertFalse(board["candidate_v12_allowed"])
        self.assertEqual(board["evidence_freshness_summary"]["status"], "blocked")
        self.assertIn("freshness:candidate_v12_report_stale", board["blocking_reasons"])
        self.assertIn("freshness:candidate_v12_report_stale", board["top_blocking_reasons"])
        self.assertEqual(board["next_allowed_action"], "refresh_stale_evidence")
        self.assertFalse(board["training_invoked"])
        self.assertFalse(board["active_updated"])
        self.assertFalse(board["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
