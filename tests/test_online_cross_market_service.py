from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.online_cross_market_service import (
    parse_alpha_fx_daily,
    parse_alpha_treasury_yield,
    refresh_online_cross_market_data,
)


class NoKeyProvider:
    api_key = ""


class FakeAlphaProvider:
    api_key = "TEST_ALPHA_1234567890"

    def fetch_fx_daily(self, **_: object) -> dict[str, object]:
        return {
            "success": True,
            "from_cache": False,
            "data": {
                "Time Series FX (Daily)": {
                    "2026-05-24": {"4. close": "7.1000"},
                    "2026-05-25": {"4. close": "7.1200"},
                }
            },
        }

    def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
        return {
            "success": True,
            "from_cache": False,
            "data": {"data": [{"date": "2026-05-25", "value": "4.25"}]},
        }

    def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
        return {
            "success": True,
            "from_cache": False,
            "data": {"data": [{"date": "2026-05-01", "value": "9800"}]},
        }


class OnlineCrossMarketServiceTest(unittest.TestCase):
    def test_alpha_vantage_key_missing_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = refresh_online_cross_market_data(provider=NoKeyProvider())

        self.assertEqual(result["status"], "key_missing")
        self.assertFalse(result["success"])
        self.assertFalse(result["client_upload_required"])

    def test_fx_daily_parser_schema(self) -> None:
        rows = parse_alpha_fx_daily({"Time Series FX (Daily)": {"2026-05-25": {"4. close": "7.12"}}})

        self.assertEqual(rows[0]["trade_date"], "2026-05-25")
        self.assertEqual(rows[0]["usd_cny"], 7.12)

    def test_treasury_yield_parser_schema(self) -> None:
        rows = parse_alpha_treasury_yield({"data": [{"date": "2026-05-25", "value": "4.25"}]})

        self.assertEqual(rows[0]["trade_date"], "2026-05-25")
        self.assertEqual(rows[0]["us10y"], 4.25)

    def test_refresh_writes_cross_market_rows_without_customer_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = refresh_online_cross_market_data(provider=FakeAlphaProvider())
            data_path = Path(tmp) / "outputs" / "fundamentals" / "sn_cross_market.json"
            payload = json.loads(data_path.read_text(encoding="utf-8"))

        self.assertTrue(result["success"])
        self.assertGreater(result["row_count"], 0)
        self.assertFalse(result["client_upload_required"])
        self.assertIn("usd_cny", str(payload))
        self.assertIn("us10y", str(payload))


if __name__ == "__main__":
    unittest.main()
