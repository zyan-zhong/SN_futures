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


class ManagedDataQualityDecisionBoardTest(unittest.TestCase):
    def test_quality_fail_sets_next_action_to_fix_managed_data_quality(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            diagnostics.mkdir(parents=True, exist_ok=True)
            (diagnostics / "managed_proxy_config_wizard_report.json").write_text(json.dumps({"status": "ready", "blocking_reasons": []}), encoding="utf-8")
            (diagnostics / "managed_proxy_setup_report.json").write_text(json.dumps({"status": "ready", "managed_proxy_health_allowed": True, "blocking_reasons": []}), encoding="utf-8")
            (diagnostics / "managed_proxy_schema_mapping_report.json").write_text(json.dumps({"status": "ready", "schema_mapping_ready": True, "blocking_reasons": []}), encoding="utf-8")
            (diagnostics / "managed_proxy_health.json").write_text(json.dumps({"status": "ready", "ready": True, "v12_allowed": True, "blocking_reasons": []}), encoding="utf-8")
            (diagnostics / "managed_proxy_reliability_report.json").write_text(json.dumps({"status": "pass", "blocking_reasons": []}), encoding="utf-8")
            (diagnostics / "managed_data_quality_scorecard.json").write_text(
                json.dumps({"status": "fail", "gate_passed": False, "blocking_reasons": ["negative_inventory"], "warning_reasons": []}),
                encoding="utf-8",
            )

            board = build_research_decision_board()

        self.assertEqual(board["current_research_state"], "managed_data_blocked")
        self.assertEqual(board["next_allowed_action"], "fix_managed_data_quality")
        self.assertIn("managed_data_quality:negative_inventory", board["blocking_reasons"])
        self.assertFalse(board["candidate_training_allowed"])


if __name__ == "__main__":
    unittest.main()
