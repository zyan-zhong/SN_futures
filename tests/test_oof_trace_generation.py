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
from sn_futures.services.walk_forward_training_service import run_candidate_training


def _write_history(root: str, rows: int = 220) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2024-01-01", periods=rows, freq="D")):
        close = 210000.0 + idx * 65.0 + (idx % 9) * 120.0
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 180,
                "high": close + 520,
                "low": close - 520,
                "close": close,
                "volume": 8000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class OOFTraceGenerationTest(unittest.TestCase):
    def test_candidate_walk_forward_writes_oof_trace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            build_training_dataset(horizons=(1,), min_feature_coverage=0.7)
            result = run_candidate_training(["1d"])

            trace_path = Path(result["oof_trace_paths"]["1d"])
            self.assertTrue(trace_path.exists())
            frame = pd.read_csv(trace_path)
            self.assertGreater(len(frame), 0)
            self.assertTrue(frame["fold_id"].notna().all())
            self.assertTrue(frame["label_end_time"].notna().all())
            self.assertIn("is_high_confidence_top_10", frame.columns)
            self.assertFalse(result["active_updated"])
            self.assertFalse(result["customer_prediction_generated"])
            self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()
