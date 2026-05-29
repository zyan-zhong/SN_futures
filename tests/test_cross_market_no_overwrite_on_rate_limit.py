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


class RateLimitedProvider:
    api_key = "TEST_ALPHA_NO_OVERWRITE"

    def fetch_fx_daily(self, **_: object) -> dict[str, object]:
        return {"success": True, "from_cache": False, "message": "ok", "data": {"Information": "standard API rate limit"}}

    def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
        return self.fetch_fx_daily()

    def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
        return self.fetch_fx_daily()


class CrossMarketNoOverwriteOnRateLimitTest(unittest.TestCase):
    def test_rate_limit_does_not_overwrite_non_empty_cross_market_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            existing = [{"trade_date": "2026-05-25", "usd_cny": 7.12, "us10y": 4.25}]
            data_path = fundamentals / "sn_cross_market.json"
            data_path.write_text(json.dumps({"rows": existing}), encoding="utf-8")

            result = refresh_cross_market_backfill(provider=RateLimitedProvider(), max_endpoints_per_run=3)
            after = json.loads(data_path.read_text(encoding="utf-8"))
            status = json.loads((fundamentals / "fx_macro_provider_status.json").read_text(encoding="utf-8"))

        self.assertEqual(after["rows"], existing)
        self.assertEqual(status["status"], "using_cache_rate_limited")
        self.assertEqual(result["status"], "using_cache_rate_limited")
        self.assertTrue(result["from_cache"])


if __name__ == "__main__":
    unittest.main()
