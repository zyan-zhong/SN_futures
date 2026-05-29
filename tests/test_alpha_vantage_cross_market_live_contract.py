from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.online_cross_market_service import refresh_online_cross_market_data


class FakeAlphaProvider:
    api_key = "FAKE_ALPHA_1234567890"

    def fetch_exchange_rate(self, **_: object) -> dict[str, object]:
        return {
            "success": True,
            "from_cache": False,
            "message": "ok",
            "data": {"Realtime Currency Exchange Rate": {"5. Exchange Rate": "7.1800", "6. Last Refreshed": "2026-05-25 12:00:00"}},
        }

    def fetch_fx_daily(self, **_: object) -> dict[str, object]:
        return {
            "success": True,
            "from_cache": False,
            "message": "ok",
            "data": {"Time Series FX (Daily)": {"2026-05-24": {"4. close": "7.10"}, "2026-05-25": {"4. close": "7.18"}}},
        }

    def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
        return {"success": True, "from_cache": False, "message": "ok", "data": {"data": [{"date": "2026-05-25", "value": "4.25"}]}}

    def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
        return {"success": True, "from_cache": False, "message": "ok", "data": {"data": [{"date": "2026-05-01", "value": "10000"}]}}


class AlphaVantageCrossMarketContractTest(unittest.TestCase):
    def test_key_missing_returns_key_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.api_key_resolver.read_project_env_values", return_value={}
        ):
            os.environ.pop("SN_ALPHA_VANTAGE_KEY", None)
            result = refresh_online_cross_market_data()

        self.assertEqual(result["status"], "key_missing")

    def test_fixture_success_writes_usd_cny_and_us10y(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = refresh_online_cross_market_data(provider=FakeAlphaProvider())  # type: ignore[arg-type]
            path = Path(tmp) / "outputs" / "fundamentals" / "sn_cross_market.json"
            payload = json.loads(path.read_text(encoding="utf-8"))

        self.assertTrue(result["success"])
        rows = payload["rows"]
        self.assertTrue(any(row.get("usd_cny") for row in rows))
        self.assertTrue(any(row.get("us10y") for row in rows))
        self.assertFalse(any(row.get("lme_tin_close") for row in rows))

    def test_rate_limit_response_is_classified(self) -> None:
        class RateLimitProvider(FakeAlphaProvider):
            def fetch_exchange_rate(self, **_: object) -> dict[str, object]:
                return {"success": False, "from_cache": False, "message": "Thank you for using Alpha Vantage rate limit", "error_code": "rate_limited", "data": None}

            def fetch_fx_daily(self, **_: object) -> dict[str, object]:
                return self.fetch_exchange_rate()

            def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
                return self.fetch_exchange_rate()

            def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
                return self.fetch_exchange_rate()

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = refresh_online_cross_market_data(provider=RateLimitProvider())  # type: ignore[arg-type]

        self.assertEqual(result["status"], "rate_limited")


if __name__ == "__main__":
    unittest.main()
