from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.training_dataset_service import build_training_dataset, get_training_dataset_status


def _write_history(root: str, rows: int = 80, sample: bool = False) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2025-01-01", periods=rows, freq="D")):
        close = 200000.0 + idx * 100.0
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 200,
                "high": close + 500,
                "low": close - 600,
                "close": close,
                "volume": 10000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(
        json.dumps({"sample": sample, "history": history}, ensure_ascii=False),
        encoding="utf-8",
    )


class TrainingDatasetServiceTest(unittest.TestCase):
    def test_build_training_dataset_from_real_market_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp, rows=90)
            manifest = build_training_dataset(horizons=(1, 3, 5), min_feature_coverage=0.7)
            status = get_training_dataset_status()
            output = Path(tmp) / "outputs"
            self.assertEqual(manifest["status"], "success")
            self.assertTrue((output / "training_dataset_manifest.json").exists())
            self.assertEqual(status["status"], "success")
            self.assertFalse(manifest["sample_data_used"])
            self.assertFalse(manifest["baseline_used"])
            self.assertGreater(manifest["feature_count"], 0)
            self.assertEqual(manifest["sample_count_by_horizon"]["1d"], 89)
            self.assertEqual(manifest["sample_count_by_horizon"]["5d"], 85)

    def test_sample_data_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp, rows=90, sample=True)
            with self.assertRaises(ValueError):
                build_training_dataset(horizons=(1,))

    def test_manifest_paths_exist_and_no_predictions_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp, rows=90)
            manifest = build_training_dataset(horizons=(1, 3))
            output = Path(tmp) / "outputs"
            files = {path.name for path in output.glob("*")}
            for dataset_path in manifest["dataset_paths"].values():
                self.assertTrue(Path(dataset_path).exists())
            self.assertNotIn("sn_live_predictions.json", files)
            self.assertNotIn("sn_unified_forecast.json", files)


if __name__ == "__main__":
    unittest.main()
