from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

from candidate_v6_research_fixtures import successful_candidate, successful_dataset, write_ready_v6_inputs
from sn_futures.services.candidate_v6_gated_research_service import run_candidate_v6_gated_research


class CandidateV6InstitutionalValidationTest(unittest.TestCase):
    def test_pipeline_records_institutional_validation_evidence_for_v6(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            write_ready_v6_inputs(output)
            validation_payload = {
                "status": "failed",
                "passed": False,
                "candidate_version": "v6",
                "dry_run": True,
                "deflated_sharpe_ratio": {"deflated_sharpe_ratio": 0.12},
                "probability_of_backtest_overfitting": {"pbo": 0.34},
                "reality_check": {"p_value": 0.18, "passed": False},
                "cost_stress": {"2x_cost": {"expectancy": -0.001}, "3x_cost": {"expectancy": -0.002}},
                "feature_stability": {"stability_score": 0.72, "passed": True},
                "active_updated": False,
                "customer_prediction_generated": False,
            }
            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset", return_value=successful_dataset()), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training", return_value=successful_candidate(output)), \
                patch("sn_futures.services.candidate_v6_gated_research_service.get_oof_integrity_report", return_value={"status": "success"}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_research_backtest", return_value={"status": "success"}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_institutional_validation", return_value=validation_payload), \
                patch("sn_futures.services.candidate_v6_gated_research_service.promote_candidate", return_value={"status": "failed", "passed": False, "dry_run": True, "active_updated": False}):
                result = run_candidate_v6_gated_research(horizons=("1d",))

        validation = result["institutional_validation"]
        self.assertEqual(validation["candidate_version"], "v6")
        self.assertIn("deflated_sharpe_ratio", validation)
        self.assertIn("probability_of_backtest_overfitting", validation)
        self.assertIn("reality_check", validation)
        self.assertIn("2x_cost", validation["cost_stress"])
        self.assertFalse(validation["active_updated"])


if __name__ == "__main__":
    unittest.main()
