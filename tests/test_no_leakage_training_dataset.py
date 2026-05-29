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

from sn_futures.services.training_dataset_service import FORBIDDEN_FEATURE_PATTERNS, build_training_dataset


def _write_history(root: str, rows: int = 100) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2025-01-01", periods=rows, freq="D")):
        close = 300000.0 + idx * 50
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 100,
                "high": close + 400,
                "low": close - 500,
                "close": close,
                "volume": 5000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class NoLeakageTrainingDatasetTest(unittest.TestCase):
    def test_label_columns_are_not_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            manifest = build_training_dataset(horizons=(1, 3, 5))
        self.assertTrue(manifest["leakage_check_pass"])
        for column in manifest["feature_cols"]:
            self.assertFalse(column.startswith(tuple(FORBIDDEN_FEATURE_PATTERNS)), column)
        for label in ("ret_1d", "direction_1d", "tb_label_1d"):
            self.assertIn(label, manifest["label_cols"])
            self.assertNotIn(label, manifest["feature_cols"])

    def test_dataset_contains_label_times_and_tail_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp, rows=50)
            manifest = build_training_dataset(horizons=(10,))
            dataset_path = Path(manifest["dataset_paths"]["10d"])
            if dataset_path.suffix == ".parquet":
                data = pd.read_parquet(dataset_path)
            else:
                data = pd.read_csv(dataset_path)
        self.assertEqual(len(data), 40)
        self.assertIn("label_start_time", data.columns)
        self.assertIn("label_end_time", data.columns)
        self.assertTrue((pd.to_datetime(data["label_end_time"]) > pd.to_datetime(data["label_start_time"])).all())


if __name__ == "__main__":
    unittest.main()
