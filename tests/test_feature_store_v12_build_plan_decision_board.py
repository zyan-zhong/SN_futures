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


class FeatureStoreV12BuildPlanDecisionBoardTest(unittest.TestCase):
    def test_build_plan_ready_does_not_mark_v12_built_or_candidate_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            _write_json(
                out / "diagnostics" / "feature_store_v12_build_plan_report.json",
                {
                    "status": "ready",
                    "feature_store_v12_build_executed": False,
                    "blocking_reasons": [],
                    "expected_feature_store_path": str(out / "feature_store" / "v12" / "feature_store.csv"),
                },
            )
            _write_json(
                out / "diagnostics" / "managed_data_production_cache_gate_report.json",
                {"status": "blocked", "production_cache_written": False, "blocking_reasons": ["production_cache_not_written"]},
            )
            board = build_research_decision_board()

        self.assertFalse(board["candidate_training_allowed"])
        self.assertFalse(board["training_dataset_v12_allowed"])
        self.assertIn("feature_store_v12_build_plan", board["evidence_paths"])
        self.assertEqual(board["feature_store_v12_build_plan_summary"]["status"], "ready")
        self.assertFalse(board["feature_store_v12_build_plan_summary"]["feature_store_v12_build_executed"])


if __name__ == "__main__":
    unittest.main()
