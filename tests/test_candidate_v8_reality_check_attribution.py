from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from candidate_v8_diagnostics_fixtures import write_v8_diagnostics_fixture
from sn_futures.services.candidate_v8_diagnostics_service import build_candidate_v8_validation_diagnostics


class CandidateV8RealityCheckAttributionTest(unittest.TestCase):
    def test_outputs_reality_check_gap_and_causes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            write_v8_diagnostics_fixture(Path(tmp))
            result = build_candidate_v8_validation_diagnostics()

        reality = result["reality_check_bootstrap_summary"]
        self.assertEqual(reality["p_value"], 0.0575)
        self.assertAlmostEqual(reality["gap_to_threshold"], 0.0075, places=4)
        self.assertEqual(reality["threshold"], 0.05)
        self.assertIn("near_threshold_not_passed", reality["root_causes"])
        self.assertIn("increase_independent_trade_count", [item["action"] for item in result["recommended_v9_actions"]])


if __name__ == "__main__":
    unittest.main()
