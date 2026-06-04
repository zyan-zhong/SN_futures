from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.research_decision_board_service import build_research_decision_board


def _write_ready_upstream(diagnostics: Path) -> None:
    diagnostics.mkdir(parents=True, exist_ok=True)
    (diagnostics / "managed_proxy_config_wizard_report.json").write_text(json.dumps({"status": "ready"}), encoding="utf-8")
    (diagnostics / "managed_proxy_setup_report.json").write_text(
        json.dumps({"status": "ready", "managed_proxy_health_allowed": True, "blocking_reasons": []}),
        encoding="utf-8",
    )
    (diagnostics / "managed_proxy_endpoint_smoke_report.json").write_text(
        json.dumps({"status": "pass", "auth_status": "pass", "endpoint_reachable": True, "response_format_status": "pass", "token_echo_status": "pass"}),
        encoding="utf-8",
    )
    (diagnostics / "managed_proxy_quarantine_snapshot_report.json").write_text(
        json.dumps({"status": "ready", "snapshot_pulled": True, "feature_store_v12_allowed": False, "production_eligible": False}),
        encoding="utf-8",
    )


class ManagedProxyQuarantineContractDecisionBoardTest(unittest.TestCase):
    def test_quarantine_contract_failure_points_to_fix_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            _write_ready_upstream(diagnostics)
            (diagnostics / "managed_proxy_quarantine_contract_report.json").write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "schema_contract_status": "blocked",
                        "research_cache_promotion_allowed": False,
                        "feature_store_v12_allowed": False,
                        "blocking_reasons": ["managed_proxy_schema_mapping_blocked"],
                    }
                ),
                encoding="utf-8",
            )

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "fix_quarantine_contract_failures")
        self.assertEqual(board["managed_proxy_summary"]["quarantine_contract_status"], "blocked")
        self.assertFalse(board["training_dataset_v12_allowed"])
        self.assertFalse(board["candidate_training_allowed"])

    def test_quarantine_contract_ready_points_to_real_backfill_planner_not_v12_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            _write_ready_upstream(diagnostics)
            (diagnostics / "managed_proxy_quarantine_contract_report.json").write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "schema_contract_status": "ready",
                        "pit_replay_status": "ready",
                        "pit_audit_status": "ready",
                        "data_quality_status": "pass",
                        "research_cache_promotion_allowed": True,
                        "research_cache_written": True,
                        "production_eligible": False,
                        "feature_store_v12_allowed": False,
                        "blocking_reasons": [],
                    }
                ),
                encoding="utf-8",
            )

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "run_real_managed_data_backfill_planner")
        self.assertEqual(board["managed_proxy_summary"]["quarantine_contract_status"], "ready")
        self.assertFalse(board["training_dataset_v12_allowed"])
        self.assertFalse(board["candidate_training_allowed"])


if __name__ == "__main__":
    unittest.main()
