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
        {
            "status": "ready",
            "research_cache_promotion_allowed": True,
            "research_cache_written": True,
            "production_eligible": False,
            "feature_store_v12_allowed": False,
            "blocking_reasons": [],
        },
    )


class ManagedDataBackfillPlannerDecisionBoardTest(unittest.TestCase):
    def test_ready_backfill_plan_does_not_unlock_feature_store_or_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            _write_ready_upstream(diagnostics)
            _write_json(
                diagnostics / "managed_data_backfill_planner_report.json",
                {
                    "status": "ready",
                    "production_cache_write_allowed": False,
                    "feature_store_v12_allowed": False,
                    "rows_fetched": False,
                    "blocking_reasons": [],
                },
            )

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertIn(board["next_allowed_action"], {"run_production_cache_promotion_gate", "review_real_managed_data_backfill_plan", "run_real_managed_data_backfill_planner"})
        self.assertEqual(board["managed_proxy_summary"]["backfill_plan_status"], "ready")
        self.assertTrue(board["managed_proxy_summary"]["backfill_plan_ready"])
        self.assertFalse(board["managed_proxy_summary"]["backfill_plan_feature_store_v12_allowed"])
        self.assertFalse(board["training_dataset_v12_allowed"])
        self.assertFalse(board["candidate_training_allowed"])
        self.assertFalse(board["active_publish_allowed"])

    def test_blocked_backfill_plan_keeps_upstream_next_action_when_setup_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            _write_json(
                diagnostics / "managed_proxy_setup_report.json",
                {
                    "status": "blocked",
                    "endpoint_configured": False,
                    "token_configured": False,
                    "blocking_reasons": ["managed_proxy_disabled"],
                    "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
                },
            )
            _write_json(
                diagnostics / "managed_data_backfill_planner_report.json",
                {"status": "blocked", "blocking_reasons": ["endpoint_smoke_not_passed"], "feature_store_v12_allowed": False},
            )

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "configure_managed_proxy_endpoint_or_token")
        self.assertFalse(board["candidate_training_allowed"])


if __name__ == "__main__":
    unittest.main()
