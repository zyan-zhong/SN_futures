from __future__ import annotations

import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.cpcv_validation_service import build_cpcv_splits, compute_path_metrics, estimate_pbo


class CPCVPBOEstimatorTest(unittest.TestCase):
    def test_estimates_pbo_by_path_from_train_selected_holdout_rank(self) -> None:
        path_metrics = [
            {
                "path_id": "path_1",
                "strategy_metrics": {
                    "overfit": {"train_metric": 0.040, "test_metric": -0.020},
                    "stable": {"train_metric": 0.020, "test_metric": 0.018},
                    "weak": {"train_metric": 0.004, "test_metric": 0.003},
                },
            },
            {
                "path_id": "path_2",
                "strategy_metrics": {
                    "overfit": {"train_metric": 0.035, "test_metric": -0.015},
                    "stable": {"train_metric": 0.019, "test_metric": 0.017},
                    "weak": {"train_metric": 0.004, "test_metric": 0.002},
                },
            },
            {
                "path_id": "path_3",
                "strategy_metrics": {
                    "overfit": {"train_metric": 0.030, "test_metric": -0.010},
                    "stable": {"train_metric": 0.020, "test_metric": 0.019},
                    "weak": {"train_metric": 0.003, "test_metric": 0.002},
                },
            },
        ]

        result = estimate_pbo(path_metrics)

        self.assertEqual(result["path_count"], 3)
        self.assertEqual(len(result["pbo_by_path"]), 3)
        self.assertGreaterEqual(result["pbo"], 0.9)
        self.assertEqual({row["selected_strategy"] for row in result["pbo_by_path"]}, {"overfit"})
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_compute_path_metrics_evaluates_precomputed_signals_without_training(self) -> None:
        y_return = np.tile([0.01, -0.008, 0.012, -0.009], 20)
        direction = np.sign(y_return)
        frame = pd.DataFrame(
            {
                "y_return": y_return,
                "stable_signal": direction,
                "inverse_signal": -direction,
            }
        )
        splits = build_cpcv_splits(sample_count=len(frame), n_groups=4, test_group_count=1, purge=1, embargo=1)

        metrics = compute_path_metrics(frame, splits, strategy_columns=["stable_signal", "inverse_signal"])

        self.assertEqual(len(metrics), 4)
        self.assertIn("stable_signal", metrics[0]["strategy_metrics"])
        self.assertGreater(metrics[0]["strategy_metrics"]["stable_signal"]["test_metric"], 0)
        self.assertLess(metrics[0]["strategy_metrics"]["inverse_signal"]["test_metric"], 0)
        self.assertTrue(metrics[0]["research_only"])


if __name__ == "__main__":
    unittest.main()
