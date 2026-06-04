from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from regime_balanced_v10_fixtures import seed_v7_inputs
from sn_futures.services.regime_balanced_dataset_service import build_training_dataset_v10


class RegimeBalancedManifestTest(unittest.TestCase):
    def test_manifest_records_horizon_regime_counts_and_validation_samples(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            seed_v7_inputs(Path(tmp) / "outputs")
            manifest = build_training_dataset_v10(horizons=(1, 3, 5, 10, 20), min_feature_coverage=0.0)

        required_regimes = {"high_volatility", "low_volatility", "range"}
        for horizon, counts in manifest["horizon_regime_counts"].items():
            self.assertTrue(required_regimes.issubset(set(counts)))
            for regime in required_regimes:
                self.assertGreater(counts[regime], 0, f"{horizon} missing trainable {regime} samples")
                self.assertGreater(
                    manifest["horizon_regime_validation_counts"][horizon][regime],
                    0,
                    f"{horizon} missing validation {regime} samples",
                )
        self.assertEqual(manifest["regime_balance_policy"]["dominant_regime"], "high_volatility")
        self.assertEqual(manifest["regime_balance_policy"]["dominant_regime_action"], "downweight")
        self.assertEqual(manifest["regime_balance_policy"]["underrepresented_regime_action"], "boost")
        self.assertTrue(manifest["no_model_training"])


if __name__ == "__main__":
    unittest.main()
