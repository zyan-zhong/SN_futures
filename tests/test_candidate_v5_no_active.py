from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.candidate_v5_research_service import run_candidate_v5_research


class CandidateV5NoActiveTest(unittest.TestCase):
    def test_candidate_v5_dry_run_never_writes_active_or_customer_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            with patch("sn_futures.services.candidate_v5_research_service.run_candidate_training") as train, \
                patch("sn_futures.services.candidate_v5_research_service.run_research_backtest") as backtest, \
                patch("sn_futures.services.candidate_v5_research_service.run_institutional_validation") as validation, \
                patch("sn_futures.services.candidate_v5_research_service.promote_candidate") as promote, \
                patch("sn_futures.services.candidate_v5_research_service.optimize_multi_objective_research_strategy") as optimize, \
                patch("sn_futures.services.candidate_v5_research_service.archive_research_run") as archive:
                train.return_value = {"status": "success", "candidate_version": "v5"}
                backtest.return_value = {"status": "success", "horizons": {}}
                validation.return_value = {"status": "success", "passed": False}
                promote.return_value = {"status": "rejected", "dry_run": True, "active_updated": False}
                optimize.return_value = {"status": "success", "promotion_readiness": "research_only"}
                archive.return_value = {"artifact_dir": str(output / "research_runs" / "run"), "run_id": "run"}
                result = run_candidate_v5_research(horizons=("1d",))

        self.assertEqual(result["candidate_version"], "v5")
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "sn_live_predictions.json").exists())
        self.assertTrue(promote.call_args.kwargs["dry_run"])


if __name__ == "__main__":
    unittest.main()
