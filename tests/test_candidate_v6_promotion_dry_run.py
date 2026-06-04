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


class CandidateV6PromotionDryRunTest(unittest.TestCase):
    def test_promotion_is_dry_run_and_success_only_recommends_manual_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            write_ready_v6_inputs(output)

            def fake_promote(**kwargs: object) -> dict[str, object]:
                self.assertEqual(kwargs.get("candidate_version"), "v6")
                self.assertTrue(kwargs.get("dry_run"))
                return {
                    "status": "pass",
                    "passed": True,
                    "dry_run": True,
                    "candidate_version": "v6",
                    "active_updated": False,
                    "customer_prediction_generated": False,
                    "message_zh": "Promotion dry-run passed; waiting for human approval.",
                }

            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset", return_value=successful_dataset()), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training", return_value=successful_candidate(output)), \
                patch("sn_futures.services.candidate_v6_gated_research_service.get_oof_integrity_report", return_value={"status": "success"}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_research_backtest", return_value={"status": "success"}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_institutional_validation", return_value={"status": "passed", "passed": True, "dry_run": True, "active_updated": False}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.promote_candidate", side_effect=fake_promote):
                result = run_candidate_v6_gated_research(horizons=("1d",))

        self.assertTrue(result["gate_passed"])
        self.assertTrue(result["manual_approval_recommended"])
        self.assertTrue(result["promotion_dry_run"]["dry_run"])
        self.assertFalse(result["promotion_dry_run"]["active_updated"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()
