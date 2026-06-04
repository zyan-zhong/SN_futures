from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.tushare_futures_service import (
    fetch_sn_fut_daily,
    fetch_sn_holding,
    fetch_sn_settlement,
    fetch_sn_warehouse_receipt,
)


class SchemaClient:
    def fut_daily(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": "20260102", "ts_code": "SN2406.SHF", "open": 1, "high": 2, "low": 1, "close": 2, "settle": 2, "vol": 3, "oi": 4}])

    def fut_wsr(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": "20260102", "product": "锡", "symbol": "SN", "warehouse_receipt": 5}])

    def fut_settle(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": "20260102", "ts_code": "SN2406.SHF", "settle": 2, "margin_rate": 0.1, "fee_rate": 1.5}])

    def fut_holding(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": "20260102", "ts_code": "SN2406.SHF", "broker": "member", "rank": 1, "long_hld": 10, "short_hld": 8, "vol": 6}])


class TushareFundamentalSchemaTest(unittest.TestCase):
    def test_standard_output_schemas(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "TOKEN_123456789"}, clear=False):
            daily = fetch_sn_fut_daily(client=SchemaClient())
            warehouse = fetch_sn_warehouse_receipt(client=SchemaClient())
            settlement = fetch_sn_settlement(client=SchemaClient())
            holding = fetch_sn_holding(client=SchemaClient())

        self.assertEqual(set(daily["rows"][0]), {"trade_date", "contract", "open", "high", "low", "close", "settlement", "volume", "open_interest", "source", "from_cache", "quality_flag"})
        self.assertEqual(
            set(warehouse["rows"][0]),
            {
                "trade_date",
                "product",
                "warehouse",
                "warehouse_receipt",
                "warehouse_receipt_delta",
                "warehouse_receipt_delta_1w",
                "source",
                "from_cache",
                "quality_flag",
            },
        )
        self.assertEqual(
            set(settlement["rows"][0]),
            {
                "trade_date",
                "contract",
                "settlement",
                "trading_fee_rate",
                "trading_fee",
                "long_margin_rate",
                "short_margin_rate",
                "offset_today_fee",
                "source",
                "from_cache",
                "quality_flag",
            },
        )
        self.assertEqual(
            set(holding["rows"][0]),
            {
                "trade_date",
                "contract_or_product",
                "member_name",
                "long_position",
                "short_position",
                "member_net_position",
                "long_change",
                "short_change",
                "rank",
                "source",
                "from_cache",
                "quality_flag",
            },
        )


if __name__ == "__main__":
    unittest.main()
