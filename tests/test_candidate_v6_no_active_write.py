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


class CandidateV6NoActiveWriteTest(unittest.TestCase):
    def test_successful_research_pipeline_never_writes_active_or_customer_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            write_ready_v6_inputs(output)
            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset", return_value=successful_dataset()), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training", return_value=successful_candidate(output)), \
                patch("sn_futures.services.candidate_v6_gated_research_service.get_oof_integrity_report", return_value={"status": "success"}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_research_backtest", return_value={"status": "success"}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_institutional_validation", return_value={"status": "failed", "passed": False, "dry_run": True}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.promote_candidate", return_value={"status": "failed", "passed": False, "dry_run": True, "active_updated": False}):
                result = run_candidate_v6_gated_research(horizons=("1d",))

        self.assertTrue(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "sn_live_predictions.json").exists())
        self.assertFalse((output / "customer_predictions.json").exists())


if __name__ == "__main__":
    unittest.main()
