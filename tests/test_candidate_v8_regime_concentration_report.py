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


class CandidateV8RegimeConcentrationReportTest(unittest.TestCase):
    def test_outputs_dominant_regime_concentration_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            write_v8_diagnostics_fixture(Path(tmp))
            result = build_candidate_v8_validation_diagnostics()

        table = result["regime_concentration_table"]
        high_vol = next(row for row in table if row["regime"] == "high_volatility")
        self.assertGreater(high_vol["contribution"], 0.7)
        self.assertTrue(high_vol["dominant"])
        self.assertEqual(result["regime_concentration_attribution"]["dominant_regime"], "high_volatility")
        self.assertIn("single_regime_concentration", result["recommended_v9_actions"][0]["action"])


if __name__ == "__main__":
    unittest.main()
