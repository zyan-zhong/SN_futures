from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.candidate_v9_research_service import run_candidate_v9_research


class CandidateV9ResearchBacktestTest(unittest.TestCase):
    def test_candidate_v9_outputs_validation_backtest_and_dry_run_comparison(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            with (
                patch("sn_futures.services.candidate_v9_research_service.get_feature_store_status") as feature_store,
                patch("sn_futures.services.candidate_v9_research_service.get_training_dataset_status") as dataset,
                patch("sn_futures.services.candidate_v9_research_service.run_candidate_training") as training,
                patch("sn_futures.services.candidate_v9_research_service.run_research_backtest") as backtest,
                patch("sn_futures.services.candidate_v9_research_service.run_institutional_validation") as validation,
                patch("sn_futures.services.candidate_v9_research_service.promote_candidate") as promotion,
                patch("sn_futures.services.candidate_v9_research_service.archive_research_run") as archive,
                patch("sn_futures.services.candidate_v9_research_service.build_feature_stability_evidence") as stability,
                patch("sn_futures.services.candidate_v9_research_service.get_oof_integrity_report") as integrity,
            ):
                feature_store.return_value = {
                    "status": "success",
                    "version": "v7",
                    "cost_features": ["trading_fee_rate"],
                    "positioning_features": ["member_net_position"],
                    "no_lookahead_pass": True,
                }
                dataset.return_value = {
                    "status": "success",
                    "version": "v7",
                    "leakage_check_pass": True,
                    "no_lookahead_pass": True,
                    "feature_cols": ["trading_fee_rate", "member_net_position"],
                }
                training.return_value = {"status": "success", "candidate_version": "v9", "metrics_by_horizon": {}, "registry_path": ""}
                backtest.return_value = {
                    "status": "success",
                    "horizons": {"5d": {"metrics": {"trade_count": 30, "turnover": 0.02, "max_drawdown": -0.01, "cost_stress": {"2x_cost": {"expectancy": 0.01}, "3x_cost": {"expectancy": 0.009}}}}},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }
                validation.return_value = {
                    "status": "passed",
                    "passed": True,
                    "probability_of_backtest_overfitting": {"pbo": 0.0},
                    "deflated_sharpe_ratio": {"deflated_sharpe_ratio": 2.1},
                    "reality_check": {"passed": True, "p_value": 0.03},
                    "dominance_checks": {"single_regime_contribution": 0.5},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }
                promotion.return_value = {"status": "pass", "passed": True, "active_updated": False, "customer_prediction_generated": False}
                archive.return_value = {"artifact_dir": "artifact", "run_id": "run-v9"}
                stability.return_value = {"evidence_status": "success", "passed": True}
                integrity.return_value = {"status": "success"}

                result = run_candidate_v9_research(horizons=["5d"], build_missing=False)

            self.assertEqual(result["status"], "success")
            self.assertEqual(result["research_backtest"]["status"], "success")
            self.assertEqual(result["institutional_validation"]["status"], "passed")
            self.assertEqual(result["promotion_dry_run"]["status"], "pass")
            self.assertEqual(result["v8_vs_v9"]["v9"]["PBO"], 0.0)
            self.assertTrue(result["manual_approval_recommended"])


if __name__ == "__main__":
    unittest.main()
