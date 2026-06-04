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


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_ready_upstream(diagnostics: Path) -> None:
    _write_json(diagnostics / "managed_proxy_config_wizard_report.json", {"status": "ready", "blocking_reasons": []})
    _write_json(diagnostics / "managed_proxy_setup_report.json", {"status": "ready", "managed_proxy_health_allowed": True, "blocking_reasons": []})
    _write_json(
        diagnostics / "managed_proxy_endpoint_smoke_report.json",
        {"status": "pass", "auth_status": "pass", "endpoint_reachable": True, "response_format_status": "pass", "token_echo_status": "pass", "blocking_reasons": []},
    )
    _write_json(diagnostics / "managed_proxy_quarantine_snapshot_report.json", {"status": "ready", "snapshot_pulled": True, "blocking_reasons": []})
    _write_json(
        diagnostics / "managed_proxy_quarantine_contract_report.json",
        {"status": "ready", "research_cache_promotion_allowed": True, "research_cache_written": True, "production_eligible": False, "blocking_reasons": []},
    )
    _write_json(
        diagnostics / "managed_data_backfill_planner_report.json",
        {"status": "ready", "feature_store_v12_allowed": False, "production_cache_write_allowed": False, "blocking_reasons": []},
    )


class ManagedDataProductionCacheGateDecisionBoardTest(unittest.TestCase):
    def test_blocked_gate_keeps_decision_board_managed_data_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            _write_ready_upstream(diagnostics)
            _write_json(
                diagnostics / "managed_data_production_cache_gate_report.json",
                {
                    "status": "blocked",
                    "production_cache_write_allowed": False,
                    "production_cache_written": False,
                    "feature_store_v12_allowed": False,
                    "blocking_reasons": ["manual_approval_missing_or_not_approved"],
                },
            )
            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "complete_production_cache_gate_preconditions")
        self.assertEqual(board["managed_proxy_summary"]["production_cache_gate_status"], "blocked")
        self.assertFalse(board["managed_proxy_summary"]["production_cache_written"])
        self.assertFalse(board["candidate_training_allowed"])

    def test_dry_run_ready_does_not_enable_candidate_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            _write_ready_upstream(diagnostics)
            _write_json(
                diagnostics / "managed_data_production_cache_gate_report.json",
                {
                    "status": "ready",
                    "production_cache_write_allowed": False,
                    "production_cache_written": False,
                    "feature_store_v12_allowed": False,
                    "dry_run_plan": {"status": "ready"},
                    "blocking_reasons": [],
                },
            )
            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "review_production_cache_dry_run_plan")
        self.assertFalse(board["training_dataset_v12_allowed"])
        self.assertFalse(board["candidate_training_allowed"])
        self.assertFalse(board["active_publish_allowed"])


if __name__ == "__main__":
    unittest.main()
