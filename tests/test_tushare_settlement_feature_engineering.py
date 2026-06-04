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


def _market_rows(days: int = 30) -> list[dict]:
    start = date(2026, 1, 1)
    return [
        {
            "trade_date": (start + timedelta(days=i)).isoformat(),
            "open": 200000 + i * 10,
            "high": 201000 + i * 10,
            "low": 199000 + i * 10,
            "close": 200500 + i * 10,
            "volume": 1000 + i,
        }
        for i in range(days)
    ]


class TushareSettlementFeatureEngineeringTest(unittest.TestCase):
    def test_settlement_fee_and_margin_fields_enter_cost_features_without_overwriting_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            market = _market_rows()
            _write(out / "sn_market_history.json", {"history": market})
            _write(
                out / "fundamentals" / "sn_tushare_settlement.json",
                {
                    "rows": [
                        {
                            "trade_date": row["trade_date"],
                            "contract": "SN2606",
                            "settlement": row["close"] + 250,
                            "trading_fee": 3.0 + i * 0.01,
                            "trading_fee_rate": 0.0002,
                            "long_margin_rate": 0.12,
                            "short_margin_rate": 0.13,
                            "offset_today_fee": 1.5,
                        }
                        for i, row in enumerate(market)
                    ]
                },
            )

            manifest = build_feature_store_v7()
            frame = pd.read_csv(out / "feature_store" / "v7" / "feature_store.csv")

        self.assertEqual(manifest["status"], "success")
        for field in (
            "settlement_basis_to_close",
            "settlement_return",
            "trading_fee_rate",
            "fee_rate",
            "trading_fee_level",
            "long_margin_rate",
            "short_margin_rate",
            "margin_spread",
            "offset_today_fee",
            "intraday_cost",
            "cost_pressure_score",
        ):
            self.assertIn(field, frame.columns)
            self.assertIn(field, manifest["cost_features"])

        first = frame.iloc[0]
        self.assertEqual(float(first["close"]), float(market[0]["close"]))
        self.assertEqual(float(first["settlement"]), float(market[0]["close"] + 250))
        self.assertAlmostEqual(float(first["settlement_basis_to_close"]), 250.0)
        self.assertAlmostEqual(float(first["fee_rate"]), 0.0002)
        self.assertAlmostEqual(float(first["margin_spread"]), 0.01)
        self.assertTrue(manifest["tushare_settle_used"])
        self.assertFalse(manifest["active_model_written"])
        self.assertFalse(manifest["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
