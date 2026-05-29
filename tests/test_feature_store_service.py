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

from sn_futures.services.feature_store_service import build_feature_store, get_feature_store_status


def _write_market(root: str, periods: int = 80) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.date_range("2026-01-01", periods=periods, freq="D")):
        close = 200000.0 + idx * 100.0
        rows.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 50,
                "high": close + 300,
                "low": close - 350,
                "close": close,
                "volume": 1000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")


def _write_cross_market(root: str) -> None:
    fundamentals = Path(root) / "outputs" / "fundamentals"
    fundamentals.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx, day in enumerate(pd.date_range("2025-12-31", periods=90, freq="D")):
        rows.append(
            {
                "trade_date": day.strftime("%Y-%m-%d"),
                "usd_cny": 7.1 + idx * 0.001,
                "us10y": 4.0 + idx * 0.002,
                "copper_global_proxy": 9000 + idx,
            }
        )
    (fundamentals / "sn_cross_market.json").write_text(json.dumps({"rows": rows}, ensure_ascii=False), encoding="utf-8")


def _write_event_inputs(root: str) -> None:
    events = Path(root) / "outputs" / "events"
    events.mkdir(parents=True, exist_ok=True)
    payload = {
        "used_in_model_count": 2,
        "inputs": [
            {
                "trade_date": "2026-01-03",
                "news_count": 1,
                "used_in_model_count": 1,
                "supply_shock_score": 0.8,
                "demand_shock_score": 0.0,
                "inventory_shock_score": 0.4,
                "macro_risk_score": 0.0,
                "exchange_event_score": 0.2,
                "event_recency_decay_score": 1.0,
                "max_relevance_score": 0.9,
                "avg_relevance_score": 0.9,
            }
        ],
    }
    (events / "event_factor_inputs.json").write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class FeatureStoreServiceTest(unittest.TestCase):
    def test_build_feature_store_writes_versioned_files_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market(tmp)
            _write_cross_market(tmp)
            _write_event_inputs(tmp)
            result = build_feature_store(version="v3")
            status = get_feature_store_status(version="v3")
            store_exists = Path(result["feature_store_path"]).exists()
            manifest_exists = Path(result["manifest_path"]).exists()

        self.assertEqual(result["status"], "success")
        self.assertTrue(store_exists)
        self.assertTrue(manifest_exists)
        self.assertEqual(status["version"], "v3")
        self.assertGreater(result["row_count"], 0)
        self.assertIn("usd_cny_return", result["usable_fields"])
        self.assertIn("us10y_change", result["usable_fields"])
        self.assertIn("supply_shock_score", result["usable_fields"])
        self.assertFalse(result["sample_data_used"])
        self.assertFalse(result["baseline_used"])
        self.assertTrue(result["leakage_check_pass"])


if __name__ == "__main__":
    unittest.main()
