from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.candidate_v10_research_service import run_candidate_v10_research


class CandidateV10TrainingGateTest(unittest.TestCase):
    def test_candidate_v10_blocks_when_dataset_v10_is_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            with (
                patch("sn_futures.services.candidate_v10_research_service.get_training_dataset_status") as dataset,
                patch("sn_futures.services.candidate_v10_research_service.run_candidate_training") as training,
            ):
                dataset.return_value = {
                    "status": "not_built",
                    "dataset_version": "v10",
                    "exists": False,
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                }

                result = run_candidate_v10_research(horizons=["5d"], build_missing=False)

        self.assertEqual(result["candidate_version"], "v10")
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertTrue(result["blocking_reasons"])
        training.assert_not_called()

    def test_candidate_v10_blocks_on_leakage_or_sample_mock_baseline_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            with (
                patch("sn_futures.services.candidate_v10_research_service.get_training_dataset_status") as dataset,
                patch("sn_futures.services.candidate_v10_research_service.run_candidate_training") as training,
            ):
                dataset.return_value = {
                    "status": "success",
                    "dataset_version": "v10",
                    "leakage_check_pass": False,
                    "no_lookahead_pass": False,
                    "sample_data_used": True,
                    "mock_data_used": False,
                    "baseline_used": False,
                    "regime_distribution": {"low_volatility": 10, "range": 12, "high_volatility": 8},
                    "horizon_regime_counts": {"5d": {"low_volatility": 10, "range": 12, "high_volatility": 8}},
                    "regime_sample_weights": {"5d": {"low_volatility": 1.2, "range": 1.0, "high_volatility": 0.6}},
                }

                result = run_candidate_v10_research(horizons=["5d"], build_missing=False)

        self.assertEqual(result["status"], "blocked")
        self.assertIn("leakage_check_failed", result["blocking_reasons"])
        self.assertIn("sample_data_used", result["blocking_reasons"])
        self.assertFalse(result["training_invoked"])
        training.assert_not_called()


if __name__ == "__main__":
    unittest.main()
