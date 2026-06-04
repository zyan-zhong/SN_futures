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


class FeatureStoreV12ControlledBuildDecisionBoardTest(unittest.TestCase):
    def test_controlled_build_blocked_does_not_allow_td_or_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            _write_json(
                out / "diagnostics" / "feature_store_v12_controlled_build_report.json",
                {
                    "status": "blocked",
                    "build_executed": False,
                    "blocking_reasons": ["production_cache_gate_blocked"],
                    "feature_store_v12_path": str(out / "feature_store" / "v12" / "feature_store.csv"),
                },
            )

            board = build_research_decision_board()

        self.assertFalse(board["training_dataset_v12_allowed"])
        self.assertFalse(board["candidate_v12_allowed"])
        self.assertIn("feature_store_v12_controlled_build", board["evidence_paths"])
        self.assertEqual(board["feature_store_v12_controlled_build_summary"]["status"], "blocked")
        self.assertFalse(board["feature_store_v12_controlled_build_summary"]["build_executed"])


if __name__ == "__main__":
    unittest.main()
