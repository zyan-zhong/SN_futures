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


class CandidateV8PboAttributionTest(unittest.TestCase):
    def test_outputs_pbo_attribution_by_fold_year_regime_and_horizon(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            write_v8_diagnostics_fixture(Path(tmp))
            result = build_candidate_v8_validation_diagnostics()

        pbo = result["pbo_attribution"]
        self.assertGreaterEqual(pbo["summary"]["pbo"], 0.0)
        self.assertTrue(pbo["pbo_attribution_by_fold"])
        self.assertTrue(pbo["pbo_attribution_by_year"])
        self.assertTrue(pbo["pbo_attribution_by_regime"])
        self.assertTrue(pbo["pbo_attribution_by_horizon"])
        self.assertTrue(any(row["overfit"] for row in pbo["pbo_attribution_by_fold"]))
        self.assertTrue(any(row["regime"] == "high_volatility" for row in pbo["pbo_attribution_by_regime"]))


if __name__ == "__main__":
    unittest.main()
