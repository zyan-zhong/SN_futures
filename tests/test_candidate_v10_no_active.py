from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.candidate_v10_research_service import run_candidate_v10_research


class CandidateV10NoActiveTest(unittest.TestCase):
    def test_candidate_v10_dry_run_never_writes_active_or_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
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
                patch("sn_futures.services.candidate_v10_research_service.build_cpcv_report", return_value={"status": "success", "candidate_version": "v10", "split_count": 15, "pbo": {"pbo": 0.1}, "reality_check": {"passed": True, "aggregate_p_value": 0.02}, "active_updated": False, "customer_prediction_generated": False}),
                patch("sn_futures.services.candidate_v10_research_service.run_research_backtest", return_value={"status": "success", "horizons": {}, "active_updated": False, "customer_prediction_generated": False}),
                patch("sn_futures.services.candidate_v10_research_service.run_institutional_validation", return_value={"status": "passed", "passed": True, "dominance_checks": {"single_regime_contribution": 0.3}, "cost_stress": {"2x_cost": {"expectancy": 0.01}, "3x_cost": {"expectancy": 0.008}}, "active_updated": False, "customer_prediction_generated": False}),
                patch("sn_futures.services.candidate_v10_research_service.promote_candidate") as promotion,
                patch("sn_futures.services.candidate_v10_research_service.archive_research_run", return_value={"artifact_dir": str(output / "research_runs" / "v10"), "run_id": "v10-test"}),
                patch("sn_futures.services.candidate_v10_research_service.build_feature_stability_evidence", return_value={"evidence_status": "success", "passed": True}),
                patch("sn_futures.services.candidate_v10_research_service.get_oof_integrity_report", return_value={"status": "success"}),
            ):
                promotion.return_value = {"status": "pass", "passed": True, "active_updated": False, "customer_prediction_generated": False}

                result = run_candidate_v10_research(horizons=["5d"], build_missing=False)

        promotion.assert_called_once_with(candidate_version="v10", dry_run=True)
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "customer_predictions.json").exists())


if __name__ == "__main__":
    unittest.main()
