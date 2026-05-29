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

from sn_futures.services.feature_store_service import build_feature_store
from sn_futures.services.research_v3_service import run_candidate_v3_research
from sn_futures.services.training_dataset_service import build_training_dataset


def _write_market(root: str, periods: int = 170) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.date_range("2025-01-01", periods=periods, freq="D")):
        close = 200000.0 + idx * 70.0 + (idx % 9) * 30.0
        rows.append({"time": day.strftime("%Y-%m-%d"), "open": close - 80, "high": close + 260, "low": close - 260, "close": close, "volume": 1000 + idx})
    (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")


class CandidateV3PipelineTest(unittest.TestCase):
    def test_candidate_v3_pipeline_writes_research_outputs_without_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market(tmp)
            build_feature_store(version="v3")
            build_training_dataset(dataset_version="v3", feature_store_version="v3")
            result = run_candidate_v3_research(horizons=("1d", "3d"))
            output = Path(tmp) / "outputs"
            oof_exists = (output / "walk_forward" / "v3" / "oof_trace_1d.csv").exists()
            equity_exists = (output / "research_backtests" / "v3" / "equity_curve_1d.csv").exists()
            optimization_exists = (output / "model_research" / "strategy_optimization" / "v3" / "optimization_report.json").exists()
            artifact_exists = Path(result["artifact_dir"]).exists()
            active_exists = (output / "model_registry" / "active_model.json").exists()
            prediction_exists = (output / "sn_live_predictions.json").exists()

        self.assertEqual(result["candidate_version"], "v3")
        self.assertEqual(result["status"], "success")
        self.assertTrue(oof_exists)
        self.assertTrue(equity_exists)
        self.assertTrue(optimization_exists)
        self.assertTrue(artifact_exists)
        self.assertFalse(active_exists)
        self.assertFalse(prediction_exists)
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
