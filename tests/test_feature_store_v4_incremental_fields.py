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

from sn_futures.services.feature_store_v4_service import build_feature_store_v4, build_training_dataset_v4


def _write_market(root: str, periods: int = 160) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.date_range("2025-09-01", periods=periods, freq="D")):
        close = 200000.0 + idx * 80.0
        rows.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 80.0,
                "high": close + 300.0,
                "low": close - 300.0,
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
    for day in pd.date_range("2025-09-05", periods=130, freq="D"):
        inputs.append(
            {
                "trade_date": day.strftime("%Y-%m-%d"),
                "news_count": 1,
                "used_in_model_count": 1,
                "supply_shock_score": 0.5,
                "exchange_event_score": 0.2,
                "source_reliability_weighted_score": 0.75,
                "event_recency_decay_score": 1.0,
                "max_relevance_score": 0.8,
                "avg_relevance_score": 0.8,
            }
        )
    inputs.append(
        {
            "trade_date": "2025-09-10",
            "used_in_model": False,
            "news_count": 9,
            "supply_shock_score": 9.0,
            "max_relevance_score": 0.1,
        }
    )
    (events / "event_factor_inputs.json").write_text(
        json.dumps({"used_in_model_count": len(inputs) - 1, "inputs": inputs}, ensure_ascii=False),
        encoding="utf-8",
    )


class FeatureStoreV4IncrementalFieldsTest(unittest.TestCase):
    def test_v4_feature_store_and_dataset_record_incremental_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market(tmp)
            _write_cross_market(tmp)
            _write_event_inputs(tmp)
            store = build_feature_store_v4()
            dataset = build_training_dataset_v4()
            output = Path(tmp) / "outputs"

        self.assertEqual(store["status"], "success")
        self.assertIn("usd_cny_return", store["cross_market_feature_cols"])
        self.assertIn("us10y_change", store["cross_market_feature_cols"])
        self.assertIn("source_reliability_weighted_score", store["event_feature_cols"])
        self.assertIn("source_reliability_weighted_score", store["incremental_feature_cols"])
        self.assertEqual(dataset["status"], "success")
        self.assertIn("usd_cny_return", dataset["cross_market_feature_cols"])
        self.assertIn("source_reliability_weighted_score", dataset["event_feature_cols"])
        self.assertTrue(dataset["no_lookahead_pass"])
        self.assertFalse(dataset["sample_data_used"])
        self.assertFalse(dataset["baseline_used"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "sn_live_predictions.json").exists())


if __name__ == "__main__":
    unittest.main()
