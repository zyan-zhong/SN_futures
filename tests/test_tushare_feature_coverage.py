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

from sn_futures.services.feature_coverage_service import build_feature_coverage_report


def _write_history(root: str, rows: int = 180) -> list[str]:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2026-01-01", periods=rows, freq="D")
    history = []
    for idx, day in enumerate(dates):
        close = 210000 + idx * 10
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 100,
                "high": close + 200,
                "low": close - 200,
                "close": close,
                "volume": 1000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")
    return [day.strftime("%Y-%m-%d") for day in dates]


class TushareFeatureCoverageTest(unittest.TestCase):
    def test_tushare_daily_and_warehouse_improve_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            dates = _write_history(tmp)
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            daily_rows = [
                {
                    "trade_date": day,
                    "contract": "SN2406",
                    "open": 1,
                    "high": 2,
                    "low": 1,
                    "close": 2,
                    "settlement": 2,
                    "volume": 100,
                    "open_interest": 200 + idx,
                }
                for idx, day in enumerate(dates)
            ]
            warehouse_rows = [
                {"trade_date": day, "product": "锡", "warehouse_receipt": 500 + idx}
                for idx, day in enumerate(dates)
            ]
            holding_rows = [
                {"trade_date": day, "contract": "SN2406", "member_name": "member", "long_position": 50 + idx, "short_position": 20 + idx, "volume": 100, "rank": 1}
                for idx, day in enumerate(dates)
            ]
            (fundamentals / "sn_tushare_daily.json").write_text(json.dumps({"rows": daily_rows}, ensure_ascii=False), encoding="utf-8")
            (fundamentals / "sn_tushare_warehouse_receipt.json").write_text(json.dumps({"rows": warehouse_rows}, ensure_ascii=False), encoding="utf-8")
            (fundamentals / "sn_tushare_holding.json").write_text(json.dumps({"rows": holding_rows}, ensure_ascii=False), encoding="utf-8")

            report = build_feature_coverage_report()

        raw_group = next(group for group in report["groups"] if group["group"] == "raw_market")
        inventory_group = next(group for group in report["groups"] if group["group"] == "inventory")
        self.assertIn("open_interest", report["usable_feature_cols"])
        self.assertGreater(raw_group["available_feature_count"], 5)
        self.assertTrue(any(row["name"] == "warehouse_receipt_delta_1w" and row["availability"] in {"available", "partial"} for row in inventory_group["features"]))
        self.assertIn("warehouse_receipt_delta_1w", report["usable_feature_cols"])
        self.assertIn("member_net_position", report["usable_feature_cols"])


if __name__ == "__main__":
    unittest.main()
