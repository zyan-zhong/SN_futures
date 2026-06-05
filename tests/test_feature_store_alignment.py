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
                "high": close + 250,
                "low": close - 250,
                "close": close,
                "volume": 1000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": rows}, ensure_ascii=False), encoding="utf-8")


class FeatureStoreAlignmentTest(unittest.TestCase):
    def test_cross_market_forward_fill_does_not_exceed_five_trading_days(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_market(tmp)
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            rows = [
                {"trade_date": "2026-01-01", "usd_cny": 7.1, "us10y": 4.0, "copper_global_proxy": 9000.0},
                {"trade_date": "2026-01-10", "usd_cny": 7.2, "us10y": 4.2, "copper_global_proxy": 9100.0},
            ]
            (fundamentals / "sn_cross_market.json").write_text(
                json.dumps({"rows": rows}, ensure_ascii=False),
                encoding="utf-8",
            )

            result = build_feature_store(version="v3")
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))
            frame = pd.read_csv(result["feature_store_path"])

        self.assertEqual(manifest["forward_fill_rules"]["cross_market"]["max_trading_days"], 5)
        stale_rows = frame[frame["trade_date"].isin(["2026-01-07", "2026-01-08", "2026-01-09"])]
        self.assertTrue(stale_rows["_cross_market_stale"].astype(bool).all())
        self.assertTrue(stale_rows["usd_cny"].isna().all())
        refreshed = frame[frame["trade_date"] == "2026-01-10"].iloc[0]
        self.assertFalse(bool(refreshed["_cross_market_stale"]))
        self.assertAlmostEqual(float(refreshed["usd_cny"]), 7.2)


if __name__ == "__main__":
    unittest.main()
