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


class ManagedProxyQuarantineSnapshotDecisionBoardTest(unittest.TestCase):
    def test_snapshot_ready_points_to_contract_tests_without_unlocking_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
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

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "run_quarantine_contract_tests")
        self.assertEqual(board["managed_proxy_summary"]["quarantine_snapshot_status"], "ready")
        self.assertFalse(board["training_dataset_v12_allowed"])
        self.assertFalse(board["candidate_training_allowed"])

    def test_snapshot_blocked_does_not_override_setup_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            diagnostics.mkdir(parents=True, exist_ok=True)
            (diagnostics / "managed_proxy_setup_report.json").write_text(
                json.dumps({"status": "blocked", "next_allowed_action": "enable_managed_proxy"}),
                encoding="utf-8",
            )
            (diagnostics / "managed_proxy_quarantine_snapshot_report.json").write_text(
                json.dumps({"status": "blocked", "snapshot_pulled": False, "blocking_reasons": ["endpoint_smoke_not_passed"]}),
                encoding="utf-8",
            )

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "enable_managed_proxy")


if __name__ == "__main__":
    unittest.main()
