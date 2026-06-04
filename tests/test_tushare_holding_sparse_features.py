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


def _market_rows(days: int = 20) -> list[dict]:
    start = date(2026, 2, 1)
    return [
        {
            "trade_date": (start + timedelta(days=i)).isoformat(),
            "open": 210000 + i,
            "high": 211000 + i,
            "low": 209000 + i,
            "close": 210500 + i,
            "volume": 2000 + i,
        }
        for i in range(days)
    ]


class TushareHoldingSparseFeaturesTest(unittest.TestCase):
    def test_sparse_holding_features_keep_missing_days_neutral_with_availability_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            market = _market_rows()
            _write(out / "sn_market_history.json", {"history": market})
            _write(
                out / "fundamentals" / "sn_tushare_holding.json",
                {
                    "rows": [
                        {
                            "trade_date": market[3]["trade_date"],
                            "contract": "SN2606",
                            "long_position": 1200,
                            "short_position": 900,
                            "long_change": 10,
                            "short_change": -5,
                        },
                        {
                            "trade_date": market[12]["trade_date"],
                            "contract": "SN2606",
                            "long_position": 800,
                            "short_position": 1100,
                            "long_change": -8,
                            "short_change": 12,
                        },
                    ]
                },
            )

            manifest = build_feature_store_v7()
            frame = pd.read_csv(out / "feature_store" / "v7" / "feature_store.csv")

        observed = frame[frame["trade_date"] == market[3]["trade_date"]].iloc[0]
        missing = frame[frame["trade_date"] == market[0]["trade_date"]].iloc[0]
        self.assertEqual(float(observed["member_net_position"]), 300.0)
        self.assertEqual(float(observed["member_position_available_flag"]), 1.0)
        self.assertGreater(float(observed["member_position_event_score"]), 0.0)
        self.assertTrue(pd.isna(missing["member_net_position"]))
        self.assertEqual(float(missing["member_position_available_flag"]), 0.0)
        self.assertEqual(float(missing["member_position_event_score"]), 0.0)
        self.assertIn("member_net_position", manifest["sparse_features"])
        self.assertIn("member_position_available_flag", manifest["positioning_features"])
        self.assertEqual(manifest["sparse_policy"]["raw_missing_fill"], "preserve_nan")
        self.assertTrue(manifest["tushare_holding_used"])


if __name__ == "__main__":
    unittest.main()
