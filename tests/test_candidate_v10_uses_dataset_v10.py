from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.candidate_v10_research_service import run_candidate_v10_research


def _ready_dataset(tmp: str) -> dict[str, object]:
    return {
        "status": "success",
        "dataset_version": "v10",
        "feature_store_version": "v7",
        "leakage_check_pass": True,
        "no_lookahead_pass": True,
        "sample_data_used": False,
        "mock_data_used": False,
        "baseline_used": False,
        "feature_cols": ["trading_fee_rate", "member_net_position", "regime_sample_weight"],
        "dataset_paths": {"5d": str(Path(tmp) / "outputs" / "training_datasets" / "v10" / "train_5d.csv")},
        "regime_distribution": {"low_volatility": 10, "range": 12, "high_volatility": 8},
        "horizon_regime_counts": {"5d": {"low_volatility": 10, "range": 12, "high_volatility": 8}},
        "regime_sample_weights": {"5d": {"low_volatility": 1.2, "range": 1.0, "high_volatility": 0.6}},
    }


class CandidateV10UsesDatasetV10Test(unittest.TestCase):
    def test_candidate_v10_trains_from_regime_balanced_dataset_v10_and_cpcv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            with (
                patch("sn_futures.services.candidate_v10_research_service.get_training_dataset_status") as dataset,
                patch("sn_futures.services.candidate_v10_research_service.build_cpcv_report") as cpcv,
                patch("sn_futures.services.candidate_v10_research_service.run_candidate_training") as training,
                patch("sn_futures.services.candidate_v10_research_service.run_research_backtest") as backtest,
                patch("sn_futures.services.candidate_v10_research_service.run_institutional_validation") as validation,
                patch("sn_futures.services.candidate_v10_research_service.promote_candidate") as promotion,
                patch("sn_futures.services.candidate_v10_research_service.archive_research_run") as archive,
                patch("sn_futures.services.candidate_v10_research_service.build_feature_stability_evidence") as stability,
                patch("sn_futures.services.candidate_v10_research_service.get_oof_integrity_report") as integrity,
            ):
                dataset.return_value = _ready_dataset(tmp)
                training.return_value = {"status": "success", "candidate_version": "v10", "metrics_by_horizon": {}, "registry_path": ""}
                cpcv.return_value = {
                    "status": "success",
                    "candidate_version": "v10",
                    "split_count": 15,
                    "pbo": {"pbo": 0.1},
                    "reality_check": {"passed": True, "aggregate_p_value": 0.02},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }
                backtest.return_value = {
                    "status": "success",
                    "horizons": {"5d": {"metrics": {"trade_count": 10, "turnover": 0.01, "max_drawdown": -0.01, "cost_stress": {"2x_cost": {"expectancy": 0.01}, "3x_cost": {"expectancy": 0.009}}}}},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }
                validation.return_value = {
                    "status": "passed",
                    "passed": True,
                    "probability_of_backtest_overfitting": {"pbo": 0.1},
                    "deflated_sharpe_ratio": {"deflated_sharpe_ratio": 2.2},
                    "reality_check": {"passed": True, "p_value": 0.02},
                    "dominance_checks": {"single_regime_contribution": 0.35, "single_fold_contribution": 0.3, "single_year_contribution": 0.3},
                    "cost_stress": {"2x_cost": {"expectancy": 0.01}, "3x_cost": {"expectancy": 0.009}},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }
                promotion.return_value = {"status": "pass", "passed": True, "active_updated": False, "customer_prediction_generated": False}
                archive.return_value = {"artifact_dir": "artifact", "run_id": "run-v10"}
                stability.return_value = {"evidence_status": "success", "passed": True}
                integrity.return_value = {"status": "success"}

                result = run_candidate_v10_research(horizons=["5d"], build_missing=False)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["dataset_version"], "v10")
        self.assertEqual(result["feature_set"], "regime_balanced_cpcv")
        training.assert_called_once()
        kwargs = training.call_args.kwargs
        self.assertEqual(kwargs["candidate_version"], "v10")
        self.assertEqual(kwargs["dataset_version"], "v10")
        self.assertEqual(kwargs["feature_set"], "regime_balanced_cpcv")
        self.assertLessEqual(set(kwargs["models"]), {"sklearn_hist_gradient", "extra_trees", "random_forest", "huber_return", "elastic_net_return"})
        cpcv.assert_called_with(candidate_version="v10")
        self.assertTrue(result["manual_approval_recommended"])


if __name__ == "__main__":
    unittest.main()
