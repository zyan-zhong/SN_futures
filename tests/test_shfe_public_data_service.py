from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.shfe_public_data_service import (
    detect_shfe_direct_access,
    fetch_shfe_inventory_via_akshare,
    normalize_tin_symbol,
    refresh_shfe_public_data,
)


class FakeAkShareFundamentals:
    def futures_inventory_99(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"symbol": "SN", "date": "2026-01-02", "inventory": 1200},
                {"symbol": "CU", "date": "2026-01-02", "inventory": 9999},
            ]
        )

    def futures_warehouse_receipt(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": "SN", "date": "2026-01-02", "warehouse_receipt": 800}])

    def futures_spot_price(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": "SN", "date": "2026-01-02", "spot_price": 211000, "futures_close": 210200, "spot_premium": 300}])

    def futures_zh_daily_sina(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": "SN2601", "date": "2026-01-02", "open": 209000, "high": 211000, "low": 208500, "close": 210200, "volume": 10000, "open_interest": 22000}])

    def futures_member_position_rank(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": "SN2601", "date": "2026-01-02", "rank": 1, "member_name": "测试会员", "long_position": 100, "short_position": 80}])


class EmptyAkShareFundamentals:
    def futures_inventory_99(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"symbol": "CU", "date": "2026-01-02", "inventory": 9999}])


class ShfePublicDataServiceTest(unittest.TestCase):
    def test_waf_page_is_blocked_by_waf(self) -> None:
        result = detect_shfe_direct_access(fetcher=lambda: "\u4eba\u673a\u9a8c\u8bc1 captcha")

        self.assertEqual(result["status"], "blocked_by_waf")
        self.assertFalse(result["success"])

    def test_normalize_tin_symbol(self) -> None:
        self.assertEqual(normalize_tin_symbol("\u6caa\u9521"), "SN")
        self.assertEqual(normalize_tin_symbol("SN2601"), "SN")

    def test_missing_akshare_function_is_not_fatal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = fetch_shfe_inventory_via_akshare(ak_module=object())

        self.assertFalse(result["success"])
        self.assertIn(result["status"], {"function_unavailable", "no_tin_rows"})

    def test_no_tin_rows_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = fetch_shfe_inventory_via_akshare(ak_module=EmptyAkShareFundamentals())

        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "no_tin_rows")

    def test_refresh_writes_real_fundamental_files_from_fixture(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = refresh_shfe_public_data(
                ak_module=FakeAkShareFundamentals(),
                direct_fetcher=lambda: "\u4eba\u673a\u9a8c\u8bc1 captcha",
            )
            fundamentals = Path(tmp) / "outputs" / "fundamentals"

            expected = [
                "shfe_public_provider_status.json",
                "sn_shfe_inventory.json",
                "sn_shfe_warehouse_receipts.json",
                "sn_spot_basis.json",
                "sn_exchange_daily.json",
                "sn_member_positions.json",
            ]
            for filename in expected:
                self.assertTrue((fundamentals / filename).exists(), filename)

        self.assertTrue(result["success"])
        self.assertEqual(result["results"]["shfe_direct_probe"]["status"], "blocked_by_waf")
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse(result["baseline_used"])


if __name__ == "__main__":
    unittest.main()
