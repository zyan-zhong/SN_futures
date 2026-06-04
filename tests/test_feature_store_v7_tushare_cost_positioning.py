from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v7_service import build_feature_store_v7


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _market_rows(days: int = 90) -> list[dict]:
    start = date(2026, 1, 1)
    return [
        {
            "trade_date": (start + timedelta(days=i)).isoformat(),
            "open": 250000 + i * 8,
            "high": 251000 + i * 8,
            "low": 249000 + i * 8,
            "close": 250500 + i * 8,
            "volume": 5000 + i,
        }
        for i in range(days)
    ]


class FeatureStoreV7TushareCostPositioningTest(unittest.TestCase):
    def test_feature_store_v7_manifest_records_tushare_cost_positioning_and_no_model_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            market = _market_rows()
            _write(out / "sn_market_history.json", {"history": market})
            _write(out / "fundamentals" / "sn_tushare_daily.json", {"rows": [{"trade_date": row["trade_date"], "contract": "SN2606", "open_interest": 40000 + i, "settlement": row["close"] - 20} for i, row in enumerate(market)]})
            _write(out / "fundamentals" / "sn_tushare_settlement.json", {"rows": [{"trade_date": row["trade_date"], "contract": "SN2606", "settlement": row["close"] - 15, "trading_fee_rate": 0.0002, "trading_fee": 3.0, "long_margin_rate": 0.12, "short_margin_rate": 0.13, "offset_today_fee": 1.5} for row in market]})
            _write(out / "fundamentals" / "sn_tushare_holding.json", {"rows": [{"trade_date": market[i]["trade_date"], "contract": "SN2606", "long_position": 1000 + i, "short_position": 800 + i, "long_change": 3, "short_change": -2} for i in range(0, len(market), 10)]})

            manifest = build_feature_store_v7()
            frame = pd.read_csv(out / "feature_store" / "v7" / "feature_store.csv")
            self.assertTrue(Path(manifest["feature_store_path"]).exists())
            self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())
            self.assertFalse((Path(tmp) / "outputs" / "customer_predictions.json").exists())

        self.assertEqual(manifest["version"], "v7")
        self.assertEqual(manifest["status"], "success")
        self.assertEqual(manifest["row_count"], len(market))
        for field in ("fee_rate", "long_margin_rate", "short_margin_rate", "cost_pressure_score"):
            self.assertIn(field, manifest["usable_fields"])
        for field in ("member_net_position", "member_position_available_flag", "member_position_event_score", "top_member_direction_score"):
            self.assertIn(field, manifest["usable_fields"])
        self.assertIn("sparse_feature_policy", manifest)
        self.assertTrue(manifest["tushare_daily_used"])
        self.assertTrue(manifest["tushare_settle_used"])
        self.assertTrue(manifest["tushare_holding_used"])
        self.assertFalse(manifest["sample_data_used"])
        self.assertFalse(manifest["mock_data_used"])
        self.assertFalse(manifest["baseline_used"])
        self.assertFalse(manifest["active_model_written"])
        self.assertFalse(manifest["customer_prediction_generated"])
        self.assertIn("settlement", frame.columns)
        self.assertIn("close", frame.columns)


if __name__ == "__main__":
    unittest.main()
