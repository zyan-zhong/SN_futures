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


def _write_history(root: str, rows: int = 240) -> Path:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2024-01-01", periods=rows, freq="D")):
        close = 220000.0 + idx * 55.0 + (idx % 11) * 140.0
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 180,
                "high": close + 520,
                "low": close - 480,
                "close": close,
                "volume": 10000 + idx,
                "open_interest": 150000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")
    return output


class CandidateV2PipelineTest(unittest.TestCase):
    def test_candidate_v2_writes_versioned_registry_without_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            build_training_dataset(
                horizons=(1,),
                dataset_version="v2",
                feature_set="ohlcv_technical_regime_cross_market_event",
                min_feature_coverage=0.7,
            )
            result = run_candidate_training(
                horizons=("1d",),
                candidate_version="v2",
                dataset_version="v2",
                feature_set="ohlcv_technical_regime_cross_market_event",
                label_variants=("direction_thresholded", "triple_barrier_atr"),
                models=("hist_gradient_boosting", "extra_trees"),
                calibration=("sigmoid", "isotonic"),
                no_trade_filters=("low_confidence", "low_edge"),
            )

            output = Path(tmp) / "outputs"
            self.assertEqual(result["status"], "success")
            self.assertEqual(result["candidate_version"], "v2")
            self.assertEqual(result["dataset_version"], "v2")
            self.assertTrue((output / "model_registry" / "candidate_v2_model_registry.json").exists())
            self.assertFalse((output / "model_registry" / "active_model.json").exists())
            self.assertIn("1d", result["oof_trace_paths"])
            self.assertTrue(Path(result["oof_trace_paths"]["1d"]).exists())
            self.assertEqual(result["baseline_scope"], "none")
            self.assertFalse(result["baseline_used"])
            self.assertFalse(result["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
