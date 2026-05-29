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
from sn_futures.services.training_dataset_service import build_training_dataset, get_training_dataset_status


def _write_market(root: str, periods: int = 160) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.date_range("2025-09-01", periods=periods, freq="D")):
        close = 200000.0 + idx * 80.0 + (idx % 7) * 25.0
        rows.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 80,
                "high": close + 300,
                "low": close - 300,
                "close": close,
                "volume": 1200 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")


def _write_cross_market(root: str, periods: int = 170) -> None:
    fundamentals = Path(root) / "outputs" / "fundamentals"
    fundamentals.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.date_range("2025-08-28", periods=periods, freq="D")):
        rows.append(
            {
                "trade_date": day.strftime("%Y-%m-%d"),
                "usd_cny": 7.1 + idx * 0.0005,
                "us10y": 4.0 + idx * 0.001,
                "copper_global_proxy": 9000 + idx * 2,
            }
        )
    (fundamentals / "sn_cross_market.json").write_text(json.dumps({"rows": rows}, ensure_ascii=False), encoding="utf-8")


def _write_event_inputs(root: str) -> None:
    events = Path(root) / "outputs" / "events"
    events.mkdir(parents=True, exist_ok=True)
    inputs = []
    for day in pd.date_range("2025-09-05", periods=120, freq="D"):
        inputs.append(
            {
                "trade_date": day.strftime("%Y-%m-%d"),
                "news_count": 1,
                "used_in_model_count": 1,
                "supply_shock_score": 0.5,
                "exchange_event_score": 0.2,
                "event_recency_decay_score": 1.0,
                "max_relevance_score": 0.8,
                "avg_relevance_score": 0.8,
            }
        )
    (events / "event_factor_inputs.json").write_text(
        json.dumps({"used_in_model_count": len(inputs), "inputs": inputs}, ensure_ascii=False),
        encoding="utf-8",
    )


class TrainingDatasetV3Test(unittest.TestCase):
    def test_training_dataset_v3_uses_feature_store_fields_without_training_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market(tmp)
            _write_cross_market(tmp)
            _write_event_inputs(tmp)
            feature_store = build_feature_store(version="v3")
            result = build_training_dataset(
                dataset_version="v3",
                feature_store_version="v3",
                feature_set="ohlcv_technical_regime_cross_market_event",
            )
            status = get_training_dataset_status(dataset_version="v3")
            output = Path(tmp) / "outputs"
            manifest_exists = Path(result["manifest_path"]).exists()
            active_exists = (output / "model_registry" / "active_model.json").exists()
            predictions_exist = (output / "sn_live_predictions.json").exists()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["feature_store_version"], "v3")
        self.assertEqual(result["feature_store_manifest_path"], feature_store["manifest_path"])
        self.assertTrue(manifest_exists)
        self.assertIn("usd_cny_return", result["cross_market_feature_cols"])
        self.assertIn("us10y_change", result["cross_market_feature_cols"])
        self.assertIn("supply_shock_score", result["event_feature_cols"])
        self.assertFalse(result["sample_data_used"])
        self.assertFalse(result["baseline_used"])
        self.assertTrue(result["leakage_check_pass"])
        self.assertGreater(result["sample_count_by_horizon"]["1d"], 0)
        self.assertFalse(active_exists)
        self.assertFalse(predictions_exist)
        self.assertEqual(status["dataset_version"], "v3")


if __name__ == "__main__":
    unittest.main()
