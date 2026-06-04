from __future__ import annotations

import json
import os
import tempfile
import unittest
import sys
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v5_service import build_feature_store_v5


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _market_rows(n: int = 90) -> list[dict]:
    start = date(2026, 1, 1)
    return [
        {
            "trade_date": (start + timedelta(days=i)).isoformat(),
            "open": 250000 + i,
            "high": 251000 + i,
            "low": 249000 + i,
            "close": 250500 + i,
            "volume": 1000 + i,
        }
        for i in range(n)
    ]


class FeatureStoreV5FullFieldsTest(unittest.TestCase):
    def test_v5_contains_ohlcv_tushare_managed_alpha_and_event_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            out = Path(tmp) / "outputs"
            market = _market_rows()
            _write(out / "sn_market_history.json", {"history": market})
            _write(out / "fundamentals" / "sn_tushare_daily.json", {"rows": [{"trade_date": row["trade_date"], "contract": "SN2606", "open_interest": 42000 + i, "settlement": 250200 + i} for i, row in enumerate(market)]})
            _write(out / "fundamentals" / "sn_tushare_warehouse_receipt.json", {"rows": [{"trade_date": row["trade_date"], "product": "SN", "warehouse_receipt": 4000 + i} for i, row in enumerate(market)]})
            _write(out / "fundamentals" / "sn_tushare_holding.json", {"rows": [{"trade_date": row["trade_date"], "contract": "SN2606", "long_position": 20000 + i, "short_position": 18000 + i} for i, row in enumerate(market)]})
            _write(out / "fundamentals" / "managed_fundamentals.json", {"sample_data_used": False, "rows": [{"trade_date": row["trade_date"], "symbol": "SN", "spot_price": 251000 + i, "spot_futures_basis": 500 + i, "shfe_inventory": 8000 + i, "shfe_warehouse_receipt": 4100 + i, "lme_tin_close": 33500 + i, "lme_inventory": 4700 + i, "near_contract_close": 250000 + i, "far_contract_close": 249000 + i, "near_open_interest": 42000 + i, "far_open_interest": 36000 + i, "main_contract": "SN2606", "main_contract_switch_flag": 0} for i, row in enumerate(market)]})
            _write(out / "fundamentals" / "sn_cross_market.json", {"rows": [{"trade_date": row["trade_date"], "usd_cny": 7.1, "usd_cny_return": 0.001, "us10y": 4.2, "us10y_change": 0.01, "copper_global_proxy": 9500 + i, "copper_global_proxy_return": 0.002} for i, row in enumerate(market)]})
            _write(out / "events" / "event_factor_inputs.json", {"inputs": [{"trade_date": market[10]["trade_date"], "used_in_model": True, "news_count": 1, "used_in_model_count": 1, "supply_shock_score": 0.8, "max_relevance_score": 0.9}]})

            manifest = build_feature_store_v5()
            frame = pd.read_csv(out / "feature_store" / "v5" / "feature_store.csv")

            self.assertEqual(manifest["status"], "success")
            for field in ["open", "ema_spread_5_20", "zscore_close_20", "regime_trend_score", "open_interest", "settlement", "warehouse_receipt_delta_1w", "member_net_position", "spot_futures_basis", "shfe_inventory_delta_1w", "lme_tin_return_1d", "near_far_spread", "usd_cny_return", "us10y_change", "supply_shock_score"]:
                self.assertIn(field, frame.columns)
            self.assertIn("spot_futures_basis", manifest["usable_fields"])
            self.assertIn("lme_tin_return_1d", manifest["usable_fields"])
            self.assertIn("near_far_spread", manifest["usable_fields"])
            self.assertFalse(manifest["sample_data_used"])
            self.assertFalse(manifest["baseline_used"])


if __name__ == "__main__":
    unittest.main()
