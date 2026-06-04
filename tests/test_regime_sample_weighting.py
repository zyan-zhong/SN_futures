from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from regime_balanced_v10_fixtures import read_dataset, seed_v7_inputs
from sn_futures.services.regime_balanced_dataset_service import build_training_dataset_v10


class RegimeSampleWeightingTest(unittest.TestCase):
    def test_high_volatility_is_downweighted_and_low_vol_range_are_boosted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            seed_v7_inputs(Path(tmp) / "outputs")
            manifest = build_training_dataset_v10(horizons=(1,), min_feature_coverage=0.0)
            dataset = read_dataset(manifest["dataset_paths"]["1d"])

        weights = manifest["regime_sample_weights"]["1d"]
        self.assertLess(weights["high_volatility"], weights["low_volatility"])
        self.assertLess(weights["high_volatility"], weights["range"])
        self.assertLessEqual(weights["high_volatility"], 1.0)
        self.assertGreater(weights["low_volatility"], 1.0)
        self.assertGreater(weights["range"], 1.0)
        self.assertGreater(float(dataset["regime_sample_weight"].mean()), 0.9)
        self.assertLess(float(dataset["regime_sample_weight"].mean()), 1.1)


if __name__ == "__main__":
    unittest.main()
