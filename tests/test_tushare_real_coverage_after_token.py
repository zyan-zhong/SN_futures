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

from sn_futures.services.feature_coverage_service import build_feature_coverage_report
from sn_futures.services.feature_store_v5_service import build_feature_store_v5
from sn_futures.services.tushare_futures_service import refresh_tushare_futures_data


class CoverageTushareClient:
    def __init__(self, days: list[str]) -> None:
        self.days = days

    def fut_basic(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"ts_code": "SN2406.SHF", "symbol": "SN2406", "exchange": "SHFE", "name": "沪锡2406"}])

    def trade_cal(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"cal_date": day.replace("-", ""), "is_open": 1, "exchange": "SHFE"} for day in self.days])

    def fut_daily(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "trade_date": day.replace("-", ""),
                    "ts_code": "SN2406.SHF",
                    "open": 210000 + idx,
                    "high": 210100 + idx,
                    "low": 209900 + idx,
                    "close": 210050 + idx,
                    "settle": 210020 + idx,
                    "vol": 1000 + idx,
                    "oi": 3000 + idx,
                }
                for idx, day in enumerate(self.days)
            ]
        )

    def fut_wsr(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": day.replace("-", ""), "symbol": "SN", "product": "锡", "warehouse_receipt": 1200 + idx} for idx, day in enumerate(self.days)])

    def fut_settle(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": day.replace("-", ""), "ts_code": "SN2406.SHF", "settle": 210020 + idx, "margin_rate": 0.1, "fee_rate": 1.5} for idx, day in enumerate(self.days)])

    def fut_holding(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": day.replace("-", ""), "ts_code": "SN2406.SHF", "broker": "member", "rank": 1, "long_hld": 100 + idx, "short_hld": 50 + idx, "vol": 10} for idx, day in enumerate(self.days)])


class DateRangeAwareTushareClient(CoverageTushareClient):
    def __init__(self, days: list[str]) -> None:
        super().__init__(days)
        self.daily_calls: list[dict[str, object]] = []

    def fut_daily(self, **kwargs: object) -> pd.DataFrame:
        self.daily_calls.append(dict(kwargs))
        if kwargs.get("start_date") and kwargs.get("end_date"):
            return super().fut_daily(**kwargs)
        recent_days = self.days[-2:]
        return pd.DataFrame(
            [
                {
                    "trade_date": day.replace("-", ""),
                    "ts_code": "SN2406.SHF",
                    "open": 210000 + idx,
                    "high": 210100 + idx,
                    "low": 209900 + idx,
                    "close": 210050 + idx,
                    "settle": 210020 + idx,
                    "vol": 1000 + idx,
                    "oi": 3000 + idx,
                }
                for idx, day in enumerate(recent_days)
            ]
        )


def _write_market_history(output_dir: Path, rows: int = 90) -> list[str]:
    start = date(2026, 1, 1)
    days = [(start + timedelta(days=idx)).isoformat() for idx in range(rows)]
    history = [
        {"trade_date": day, "open": 210000 + idx, "high": 210100 + idx, "low": 209900 + idx, "close": 210050 + idx, "volume": 1000 + idx}
        for idx, day in enumerate(days)
    ]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sn_market_history.json").write_text(json.dumps({"sample": False, "history": history}, ensure_ascii=False), encoding="utf-8")
    return days


class TushareRealCoverageAfterTokenTest(unittest.TestCase):
    def test_tushare_real_fields_improve_coverage_and_enter_feature_store_v5_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "ENV_TUSHARE_TOKEN_123456789"}, clear=False):
            output_dir = Path(tmp) / "outputs"
            days = _write_market_history(output_dir)
            before = build_feature_coverage_report(report_version="before_tushare")
            refresh_tushare_futures_data(client=CoverageTushareClient(days), force=True)
            after = build_feature_coverage_report(report_version="after_tushare")
            feature_store = build_feature_store_v5()

        before_raw = next(group for group in before["groups"] if group["group"] == "raw_market")
        after_raw = next(group for group in after["groups"] if group["group"] == "raw_market")
        before_inventory = next(group for group in before["groups"] if group["group"] == "inventory")
        after_inventory = next(group for group in after["groups"] if group["group"] == "inventory")
        self.assertGreater(after_raw["coverage_rate"], before_raw["coverage_rate"])
        self.assertGreater(after_inventory["coverage_rate"], before_inventory["coverage_rate"])
        for field in ("open_interest", "settlement", "warehouse_receipt_delta_1w", "member_net_position"):
            self.assertIn(field, feature_store["usable_fields"])
        self.assertTrue(feature_store["tushare_used"])
        self.assertIn("open_interest", feature_store["tushare_fields"])
        self.assertFalse(feature_store["sample_data_used"])
        self.assertFalse(feature_store["mock_data_used"])
        self.assertFalse(feature_store["baseline_used"])
        self.assertTrue(feature_store["leakage_check_pass"])

    def test_live_tushare_daily_uses_market_history_date_range_for_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "ENV_TUSHARE_TOKEN_123456789"}, clear=False):
            output_dir = Path(tmp) / "outputs"
            days = _write_market_history(output_dir)
            client = DateRangeAwareTushareClient(days)

            refresh_tushare_futures_data(client=client, force=True)
            feature_store = build_feature_store_v5()

        self.assertTrue(any(call.get("start_date") and call.get("end_date") for call in client.daily_calls))
        self.assertTrue(feature_store["tushare_used"])
        self.assertIn("open_interest", feature_store["usable_fields"])
        self.assertIn("settlement", feature_store["usable_fields"])

    def test_sparse_tushare_daily_does_not_overwrite_existing_market_ohlcv(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output_dir = Path(tmp) / "outputs"
            days = _write_market_history(output_dir)
            fundamentals = output_dir / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            (fundamentals / "sn_tushare_daily.json").write_text(
                json.dumps(
                    {
                        "source": "tushare",
                        "status": "success",
                        "rows": [
                            {
                                "trade_date": days[-1],
                                "contract": "SN.SHF",
                                "open": 220000,
                                "high": 221000,
                                "low": 219000,
                                "close": 220500,
                                "settlement": 220300,
                                "volume": 2000,
                                "open_interest": 3100,
                            }
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            coverage = build_feature_coverage_report(report_version="sparse_tushare")

        raw = next(group for group in coverage["groups"] if group["group"] == "raw_market")
        open_feature = next(feature for feature in raw["features"] if feature["name"] == "open")
        self.assertGreaterEqual(open_feature["non_null_rate"], 0.9)
        self.assertGreaterEqual(raw["coverage_rate"], 0.8)


if __name__ == "__main__":
    unittest.main()
