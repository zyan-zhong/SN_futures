from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.candidate_v9_research_service import run_candidate_v9_research


class CandidateV9NoActiveTest(unittest.TestCase):
    def test_candidate_v9_research_does_not_write_active_or_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
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
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                }
                dataset.return_value = {
                    "status": "success",
                    "version": "v7",
                    "leakage_check_pass": True,
                    "no_lookahead_pass": True,
                    "sample_data_used": False,
                    "mock_data_used": False,
                    "baseline_used": False,
                    "feature_cols": ["trading_fee_rate", "member_net_position"],
                }
                training.return_value = {"status": "success", "candidate_version": "v9", "metrics_by_horizon": {}, "registry_path": ""}
                backtest.return_value = {"status": "success", "horizons": {}, "active_updated": False, "customer_prediction_generated": False}
                validation.return_value = {"status": "failed", "passed": False, "active_updated": False, "customer_prediction_generated": False}
                promotion.return_value = {"status": "failed", "passed": False, "active_updated": False, "customer_prediction_generated": False}
                archive.return_value = {"artifact_dir": str(output / "research_runs" / "v9"), "run_id": "v9-test"}
                stability.return_value = {"evidence_status": "success", "passed": True}
                integrity.return_value = {"status": "success"}

                result = run_candidate_v9_research(horizons=["5d"], build_missing=False)

            self.assertEqual(result["candidate_version"], "v9")
            self.assertTrue(result["training_invoked"])
            self.assertFalse(result["active_updated"])
            self.assertFalse(result["customer_prediction_generated"])
            self.assertFalse((output / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()
