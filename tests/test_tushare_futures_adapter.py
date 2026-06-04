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

from sn_futures.services.tushare_futures_service import (
    fetch_sn_fut_daily,
    fetch_sn_holding,
    fetch_sn_settlement,
    fetch_sn_warehouse_receipt,
    normalize_tushare_futures_symbol,
    refresh_tushare_futures_data,
)


class FakeTushareClient:
    def fut_basic(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"ts_code": "SN2406.SHF", "symbol": "SN2406", "exchange": "SHFE", "name": "沪锡2406"},
                {"ts_code": "CU2406.SHF", "symbol": "CU2406", "exchange": "SHFE", "name": "沪铜2406"},
            ]
        )

    def trade_cal(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"cal_date": "20260102", "is_open": 1, "exchange": "SHFE"}])

    def fut_daily(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "trade_date": "20260102",
                    "ts_code": "SN2406.SHF",
                    "open": 210000,
                    "high": 211000,
                    "low": 209000,
                    "close": 210500,
                    "settle": 210300,
                    "vol": 1200,
                    "oi": 3000,
                },
                {
                    "trade_date": "20260102",
                    "ts_code": "CU2406.SHF",
                    "open": 70000,
                    "high": 71000,
                    "low": 69000,
                    "close": 70500,
                    "settle": 70400,
                    "vol": 9999,
                    "oi": 8888,
                },
            ]
        )

    def fut_wsr(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"trade_date": "20260102", "symbol": "SN", "product": "锡", "warehouse_receipt": 1500},
                {"trade_date": "20260102", "symbol": "CU", "product": "铜", "warehouse_receipt": 9000},
            ]
        )

    def fut_settle(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"trade_date": "20260102", "ts_code": "SN2406.SHF", "settle": 210300, "margin_rate": 0.12, "fee_rate": 3.0},
                {"trade_date": "20260102", "ts_code": "CU2406.SHF", "settle": 70400, "margin_rate": 0.10, "fee_rate": 2.0},
            ]
        )

    def fut_holding(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "trade_date": "20260102",
                    "ts_code": "SN2406.SHF",
                    "broker": "member-a",
                    "rank": 1,
                    "vol": 100,
                    "long_hld": 80,
                    "short_hld": 40,
                },
                {
                    "trade_date": "20260102",
                    "ts_code": "CU2406.SHF",
                    "broker": "member-b",
                    "rank": 1,
                    "vol": 999,
                    "long_hld": 888,
                    "short_hld": 777,
                },
            ]
        )


class TushareFuturesAdapterTest(unittest.TestCase):
    def test_symbol_normalization_keeps_sn_only(self) -> None:
        self.assertEqual(normalize_tushare_futures_symbol("SN2406.SHF"), "SN2406")
        self.assertEqual(normalize_tushare_futures_symbol("sn2406"), "SN2406")
        self.assertEqual(normalize_tushare_futures_symbol("CU2406.SHF"), "")

    def test_fixture_writes_standardized_sn_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "TOKEN_123456789"}, clear=False):
            result = refresh_tushare_futures_data(client=FakeTushareClient(), force=True)
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            daily = json.loads((fundamentals / "sn_tushare_daily.json").read_text(encoding="utf-8"))
            warehouse = json.loads((fundamentals / "sn_tushare_warehouse_receipt.json").read_text(encoding="utf-8"))
            settlement = json.loads((fundamentals / "sn_tushare_settlement.json").read_text(encoding="utf-8"))
            holding = json.loads((fundamentals / "sn_tushare_holding.json").read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "success")
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse(result["baseline_used"])
        self.assertEqual(daily["rows"][0]["contract"], "SN2406")
        self.assertEqual(daily["rows"][0]["open_interest"], 3000)
        self.assertEqual(warehouse["rows"][0]["warehouse_receipt"], 1500)
        self.assertEqual(settlement["rows"][0]["settlement"], 210300)
        self.assertEqual(holding["rows"][0]["member_name"], "member-a")
        all_payload = json.dumps([daily, warehouse, settlement, holding], ensure_ascii=False)
        self.assertNotIn("CU2406", all_payload)

    def test_individual_fetchers_return_no_sn_rows_without_fake_data(self) -> None:
        class NoSnClient(FakeTushareClient):
            def fut_daily(self, **_: object) -> pd.DataFrame:
                return pd.DataFrame([{"trade_date": "20260102", "ts_code": "CU2406.SHF", "close": 70500}])

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "TOKEN_123456789"}, clear=False):
            result = fetch_sn_fut_daily(client=NoSnClient())

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "no_sn_rows")
        self.assertEqual(result["row_count"], 0)


if __name__ == "__main__":
    unittest.main()
