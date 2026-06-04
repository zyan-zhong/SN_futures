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


class NoSparseHoldingOverwriteTest(unittest.TestCase):
    def test_sparse_holding_does_not_overwrite_complete_market_or_tushare_daily_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            start = date(2026, 3, 1)
            market = [
                {
                    "trade_date": (start + timedelta(days=i)).isoformat(),
                    "open": 220000 + i,
                    "high": 221000 + i,
                    "low": 219000 + i,
                    "close": 220500 + i,
                    "volume": 10000 + i,
                }
                for i in range(30)
            ]
            _write(out / "sn_market_history.json", {"history": market})
            _write(out / "fundamentals" / "sn_tushare_daily.json", {"rows": [{"trade_date": row["trade_date"], "contract": "SN2606", "open_interest": 50000 + i, "settlement": row["close"] + 12} for i, row in enumerate(market)]})
            _write(out / "fundamentals" / "sn_tushare_holding.json", {"rows": [{"trade_date": market[5]["trade_date"], "contract": "SN2606", "long_position": 1000, "short_position": 950}]})

            build_feature_store_v7()
            frame = pd.read_csv(out / "feature_store" / "v7" / "feature_store.csv")

        self.assertEqual(frame["close"].notna().sum(), len(market))
        self.assertEqual(frame["open_interest"].notna().sum(), len(market))
        self.assertEqual(float(frame.iloc[0]["open_interest"]), 50000.0)
        self.assertTrue(pd.isna(frame.iloc[0]["member_net_position"]))
        self.assertEqual(float(frame.iloc[0]["member_position_available_flag"]), 0.0)
        self.assertEqual(float(frame.iloc[5]["member_net_position"]), 50.0)


if __name__ == "__main__":
    unittest.main()
