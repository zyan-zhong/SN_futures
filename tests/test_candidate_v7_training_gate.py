from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.candidate_v7_research_service import run_candidate_v7_research


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class CandidateV7TrainingGateTest(unittest.TestCase):
    def test_without_feature_store_v7_blocks_before_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.candidate_v7_research_service.run_candidate_training"
        ) as train:
            result = run_candidate_v7_research(horizons=("1d",))

        self.assertEqual(result["status"], "blocked")
        self.assertIn("feature_store_v7_missing", result["blocking_reasons"])
        self.assertFalse(result["training_invoked"])
        train.assert_not_called()

    def test_dataset_v7_leakage_fail_blocks_before_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.candidate_v7_research_service.run_candidate_training"
        ) as train:
            out = Path(tmp) / "outputs"
            _write(
                out / "feature_store" / "v7" / "feature_store_manifest.json",
                {
                    "version": "v7",
                    "status": "success",
                    "usable_fields": ["fee_rate", "member_position_available_flag"],
                    "cost_features": ["fee_rate"],
                    "positioning_features": ["member_position_available_flag"],
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                    "no_lookahead_pass": True,
                    "leakage_check_pass": True,
                },
            )
            _write(
                out / "training_dataset_manifest_v7.json",
                {
                    "dataset_version": "v7",
                    "status": "success",
                    "feature_cols": ["fee_rate", "member_position_available_flag"],
                    "leakage_check_pass": False,
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                },
            )
            result = run_candidate_v7_research(horizons=("1d",), build_missing=False)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("training_dataset_v7_leakage_failed", result["blocking_reasons"])
        self.assertFalse(result["training_invoked"])
        train.assert_not_called()


if __name__ == "__main__":
    unittest.main()
