from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.candidate_v10_research_service import run_candidate_v10_research


class CandidateV10CPCVValidationTest(unittest.TestCase):
    def test_candidate_v10_reports_cpcv_pbo_reality_and_concentration_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            ready_dataset = {
                "status": "success",
                "dataset_version": "v10",
                "leakage_check_pass": True,
                "no_lookahead_pass": True,
                "sample_data_used": False,
                "mock_data_used": False,
                "baseline_used": False,
                "feature_cols": ["regime_sample_weight", "trading_fee_rate"],
                "regime_distribution": {"low_volatility": 10, "range": 10, "high_volatility": 10},
                "horizon_regime_counts": {"5d": {"low_volatility": 10, "range": 10, "high_volatility": 10}},
                "regime_sample_weights": {"5d": {"low_volatility": 1.2, "range": 1.0, "high_volatility": 0.6}},
            }
            with (
                patch("sn_futures.services.candidate_v10_research_service.get_training_dataset_status", return_value=ready_dataset),
                patch("sn_futures.services.candidate_v10_research_service.run_candidate_training", return_value={"status": "success", "candidate_version": "v10", "metrics_by_horizon": {}, "registry_path": ""}),
                patch("sn_futures.services.candidate_v10_research_service.build_cpcv_report") as cpcv,
                patch("sn_futures.services.candidate_v10_research_service.run_research_backtest", return_value={"status": "success", "horizons": {}, "active_updated": False, "customer_prediction_generated": False}),
                patch("sn_futures.services.candidate_v10_research_service.run_institutional_validation") as validation,
                patch("sn_futures.services.candidate_v10_research_service.promote_candidate", return_value={"status": "pass", "passed": True, "active_updated": False, "customer_prediction_generated": False}),
                patch("sn_futures.services.candidate_v10_research_service.archive_research_run", return_value={"artifact_dir": "artifact", "run_id": "run-v10"}),
                patch("sn_futures.services.candidate_v10_research_service.build_feature_stability_evidence", return_value={"evidence_status": "success", "passed": True}),
                patch("sn_futures.services.candidate_v10_research_service.get_oof_integrity_report", return_value={"status": "success"}),
            ):
                cpcv.return_value = {
                    "status": "success",
                    "candidate_version": "v10",
                    "split_count": 15,
                    "pbo": {"pbo": 0.19, "path_count": 15},
                    "reality_check": {"passed": True, "aggregate_p_value": 0.049},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }
                validation.return_value = {
                    "status": "passed",
                    "passed": True,
                    "probability_of_backtest_overfitting": {"pbo": 0.19},
                    "deflated_sharpe_ratio": {"deflated_sharpe_ratio": 1.8},
                    "reality_check": {"passed": True, "p_value": 0.049},
                    "dominance_checks": {"single_regime_contribution": 0.4, "single_fold_contribution": 0.35, "single_year_contribution": 0.35},
                    "cost_stress": {"2x_cost": {"expectancy": 0.003}, "3x_cost": {"expectancy": 0.002}},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }

                result = run_candidate_v10_research(horizons=["5d"], build_missing=False)

        gates = result["v10_gate_checks"]
        self.assertTrue(gates["pbo_lt_0_2"])
        self.assertTrue(gates["reality_check_pass"])
        self.assertTrue(gates["regime_concentration_pass"])
        self.assertTrue(gates["cost_pressure_positive"])
        self.assertEqual(result["cpcv_validation"]["split_count"], 15)
        self.assertEqual(result["v10_vs_v9"]["v10"]["PBO"], 0.19)


if __name__ == "__main__":
    unittest.main()
