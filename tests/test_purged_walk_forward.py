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

from sn_futures.services.training_dataset_service import build_training_dataset
from sn_futures.services.walk_forward_training_service import run_purged_walk_forward


def _write_history(root: str, rows: int = 220) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2024-01-01", periods=rows, freq="D")):
        close = 200000.0 + idx * 80.0 + (idx % 9) * 120.0
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 150,
                "high": close + 500,
                "low": close - 500,
                "close": close,
                "volume": 10000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class PurgedWalkForwardTest(unittest.TestCase):
    def test_fold_order_and_purge_embargo_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            build_training_dataset(horizons=(1,), min_feature_coverage=0.7)
            result = run_purged_walk_forward("1d")
            folds = result["folds"]
            self.assertGreaterEqual(len(folds), 2)
            for fold in folds:
                self.assertLess(fold["train_end"], fold["validation_start"])
                self.assertGreaterEqual(fold["purged_samples"], 0)
                self.assertGreaterEqual(fold["embargo_samples"], 1)
                self.assertGreater(fold["train_samples"], 0)
                self.assertGreater(fold["validation_samples"], 0)
            self.assertEqual(result["status"], "success")
            self.assertTrue((Path(tmp) / "outputs" / "walk_forward" / "wf_1d.json").exists())


if __name__ == "__main__":
    unittest.main()
