from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

from candidate_v6_research_fixtures import write_blocked_v6_inputs
from sn_futures.services.candidate_v6_gated_research_service import run_candidate_v6_gated_research


class CandidateV6NoTrainWithoutReadinessTest(unittest.TestCase):
    def test_readiness_block_returns_report_without_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            write_blocked_v6_inputs(output)
            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset") as dataset, \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training") as trainer:
                result = run_candidate_v6_gated_research(horizons=("1d",))

        dataset.assert_not_called()
        trainer.assert_not_called()
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["training_invoked"])
        self.assertIn("candidate_v6_readiness_not_ready", result["blocking_reasons"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "sn_live_predictions.json").exists())


if __name__ == "__main__":
    unittest.main()
