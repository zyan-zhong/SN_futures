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


def _write_history(root: str, rows: int = 180) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range("2026-01-01", periods=rows, freq="D")
    history = []
    for idx, day in enumerate(dates):
        close = 210000 + idx * 20
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 100,
                "high": close + 300,
                "low": close - 300,
                "close": close,
                "volume": 10000 + idx,
                "open_interest": 20000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class FeatureCoverageWithShfeAuxTest(unittest.TestCase):
    def test_shfe_auxiliary_files_improve_basis_and_inventory_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            dates = pd.date_range("2026-01-01", periods=180, freq="D")
            inventory_rows = [
                {"trade_date": day.strftime("%Y-%m-%d"), "shfe_inventory": 1000 + idx, "shfe_inventory_delta_1w": 5, "shfe_inventory_delta_4w": 20}
                for idx, day in enumerate(dates)
            ]
            receipt_rows = [
                {"trade_date": day.strftime("%Y-%m-%d"), "shfe_warehouse_receipt": 500 + idx, "warehouse_receipt_delta_1w": 3}
                for idx, day in enumerate(dates)
            ]
            basis_rows = [
                {
                    "trade_date": day.strftime("%Y-%m-%d"),
                    "spot_price": 211000 + idx * 20,
                    "futures_close": 210000 + idx * 20,
                    "spot_premium": 200,
                    "spot_futures_basis": 1000,
                    "basis_zscore_60": 0.5,
                    "basis_percentile_252": 0.7,
                    "cash_tightness_score": 0.5,
                }
                for idx, day in enumerate(dates)
            ]
            for filename, rows in {
                "sn_shfe_inventory.json": inventory_rows,
                "sn_shfe_warehouse_receipts.json": receipt_rows,
                "sn_spot_basis.json": basis_rows,
            }.items():
                (fundamentals / filename).write_text(json.dumps({"rows": rows}, ensure_ascii=False), encoding="utf-8")

            report = build_feature_coverage_report()

        by_group = {group["group"]: group for group in report["groups"]}
        self.assertGreater(by_group["basis"]["available_feature_count"], 0)
        self.assertGreater(by_group["inventory"]["available_feature_count"], 0)


if __name__ == "__main__":
    unittest.main()
