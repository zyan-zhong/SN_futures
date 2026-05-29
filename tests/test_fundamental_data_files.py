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

from sn_futures.services.shfe_public_data_service import refresh_shfe_public_data


class FakeAkShareFiles:
    def futures_inventory_99(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": "SN", "date": "2026-01-02", "inventory": 1200}])

    def futures_warehouse_receipt(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": "SN", "date": "2026-01-02", "warehouse_receipt": 800}])

    def futures_spot_price(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": "SN", "date": "2026-01-02", "spot_price": 211000, "futures_close": 210000}])

    def futures_zh_daily_sina(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": "SN2601", "date": "2026-01-02", "close": 210000, "volume": 2000, "open_interest": 3000}])

    def futures_member_position_rank(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": "SN2601", "date": "2026-01-02", "rank": 1, "member_name": "测试会员", "long_position": 10}])


class FundamentalDataFilesTest(unittest.TestCase):
    def test_fundamental_file_schema_contains_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            refresh_shfe_public_data(ak_module=FakeAkShareFiles(), direct_fetcher=lambda: "\u4eba\u673a\u9a8c\u8bc1")
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            inventory = json.loads((fundamentals / "sn_shfe_inventory.json").read_text(encoding="utf-8"))["rows"][0]
            receipts = json.loads((fundamentals / "sn_shfe_warehouse_receipts.json").read_text(encoding="utf-8"))["rows"][0]
            basis = json.loads((fundamentals / "sn_spot_basis.json").read_text(encoding="utf-8"))["rows"][0]
            exchange = json.loads((fundamentals / "sn_exchange_daily.json").read_text(encoding="utf-8"))["rows"][0]

        self.assertIn("shfe_inventory", inventory)
        self.assertIn("shfe_warehouse_receipt", receipts)
        self.assertIn("spot_price", basis)
        self.assertIn("spot_futures_basis", basis)
        self.assertIn("open_interest", exchange)
        self.assertEqual(inventory["quality_flag"], "real")
        self.assertEqual(basis["quality_flag"], "real")


if __name__ == "__main__":
    unittest.main()
