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


class RegimeBalancedNoLookaheadTest(unittest.TestCase):
    def test_regime_labels_and_weights_use_only_label_start_information(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            seed_v7_inputs(Path(tmp) / "outputs")
            manifest = build_training_dataset_v10(horizons=(1, 20), min_feature_coverage=0.0)
            one_day = read_dataset(manifest["dataset_paths"]["1d"])
            twenty_day = read_dataset(manifest["dataset_paths"]["20d"])

        self.assertTrue(manifest["no_lookahead_pass"])
        self.assertTrue(manifest["leakage_check_pass"])
        self.assertIn("regime_balance_no_lookahead", manifest["leakage_check_details"])
        forbidden = [col for col in one_day.columns if col.startswith("future_regime") or col.startswith("next_regime")]
        self.assertEqual(forbidden, [])
        self.assertEqual(set(one_day["horizon"]), {"1d"})
        self.assertEqual(set(twenty_day["horizon"]), {"20d"})
        self.assertTrue((one_day["label_start_time"].astype(str) < one_day["label_end_time"].astype(str)).all())


if __name__ == "__main__":
    unittest.main()
