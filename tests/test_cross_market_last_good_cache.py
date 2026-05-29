from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.cross_market_backfill_service import refresh_cross_market_backfill


class SuccessProvider:
    api_key = "TEST_ALPHA_CACHE_SUCCESS"

    def fetch_fx_daily(self, **_: object) -> dict[str, object]:
        return {"success": True, "from_cache": False, "message": "ok", "data": {"Time Series FX (Daily)": {"2026-05-24": {"4. close": "7.10"}, "2026-05-25": {"4. close": "7.12"}}}}

    def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
        return {"success": True, "from_cache": False, "message": "ok", "data": {"data": [{"date": "2026-05-25", "value": "4.25"}]}}

    def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
        return {"success": True, "from_cache": False, "message": "ok", "data": {"data": [{"date": "2026-05-01", "value": "9900"}]}}


class RateLimitedProvider:
    api_key = "TEST_ALPHA_CACHE_RATE_LIMIT"

    def fetch_fx_daily(self, **_: object) -> dict[str, object]:
        return {"success": True, "from_cache": False, "message": "ok", "data": {"Note": "API call frequency limit reached"}}

    def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
        return self.fetch_fx_daily()

    def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
        return self.fetch_fx_daily()


class CrossMarketLastGoodCacheTest(unittest.TestCase):
    def test_success_writes_last_good_cross_market(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = refresh_cross_market_backfill(provider=SuccessProvider(), max_endpoints_per_run=3)
            last_good_path = Path(tmp) / "outputs" / "fundamentals" / "last_good_cross_market.json"
            payload = json.loads(last_good_path.read_text(encoding="utf-8"))

        self.assertTrue(result["success"])
        self.assertGreater(len(payload["rows"]), 0)
        self.assertFalse(payload.get("sample", True))

    def test_rate_limited_uses_last_good_when_current_file_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            cached_rows = [{"trade_date": "2026-05-25", "usd_cny": 7.12, "us10y": 4.25}]
            (fundamentals / "last_good_cross_market.json").write_text(json.dumps({"rows": cached_rows}), encoding="utf-8")
            (fundamentals / "sn_cross_market.json").write_text(json.dumps({"rows": []}), encoding="utf-8")

            result = refresh_cross_market_backfill(provider=RateLimitedProvider(), max_endpoints_per_run=3)
            current = json.loads((fundamentals / "sn_cross_market.json").read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "using_cache_rate_limited")
        self.assertTrue(result["from_cache"])
        self.assertEqual(current["rows"], cached_rows)


if __name__ == "__main__":
    unittest.main()
