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


class RegimeBalancedDatasetV10Test(unittest.TestCase):
    def test_builds_v10_manifest_and_datasets_without_model_or_prediction_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output_dir = Path(tmp) / "outputs"
            seed_v7_inputs(output_dir)

            manifest = build_training_dataset_v10(horizons=(1, 3, 5), min_feature_coverage=0.0)

            self.assertTrue(Path(manifest["manifest_path"]).exists())
            self.assertFalse((output_dir / "model_registry" / "active_model.json").exists())
            self.assertFalse((output_dir / "customer_predictions.json").exists())
            first_dataset = read_dataset(manifest["dataset_paths"]["1d"])

        self.assertEqual(manifest["dataset_version"], "v10")
        self.assertEqual(manifest["feature_store_version"], "v7")
        self.assertEqual(manifest["feature_set"], "regime_balanced_tushare_cost_positioning")
        self.assertEqual(manifest["status"], "success")
        self.assertTrue(manifest["dataset_paths"])
        self.assertIn("regime_distribution", manifest)
        self.assertIn("regime_sample_weights", manifest)
        self.assertIn("horizon_regime_counts", manifest)
        self.assertFalse(manifest["sample_data_used"])
        self.assertFalse(manifest["mock_data_used"])
        self.assertFalse(manifest["baseline_used"])
        self.assertFalse(manifest["active_model_written"])
        self.assertFalse(manifest["customer_prediction_generated"])
        self.assertIn("regime_label", first_dataset.columns)
        self.assertIn("regime_sample_weight", first_dataset.columns)


if __name__ == "__main__":
    unittest.main()
