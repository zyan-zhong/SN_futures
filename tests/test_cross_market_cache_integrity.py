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


class _RateLimitedProvider:
    api_key = "test-key"

    def fetch_exchange_rate(self, **_: object) -> dict[str, object]:
        return {"success": False, "message": "Note: frequency limit reached for apikey=test-key"}

    def fetch_fx_daily(self, **_: object) -> dict[str, object]:
        return {"success": False, "message": "Note: frequency limit reached for apikey=test-key"}

    def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
        return {"success": False, "message": "Note: frequency limit reached for apikey=test-key"}

    def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
        return {"success": False, "message": "Note: frequency limit reached for apikey=test-key"}


class CrossMarketCacheIntegrityTest(unittest.TestCase):
    def test_rate_limited_refresh_does_not_overwrite_non_empty_cross_market_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            data_path = fundamentals / "sn_cross_market.json"
            existing = {
                "generated_at": "2026-01-01T00:00:00",
                "rows": [
                    {"trade_date": "2025-01-01", "usd_cny": 7.1, "us10y": 4.2, "copper_global_proxy": 9000.0}
                ],
            }
            data_path.write_text(json.dumps(existing, ensure_ascii=False), encoding="utf-8")
            before = data_path.read_text(encoding="utf-8")

            result = refresh_online_cross_market_data(provider=_RateLimitedProvider())
            after = data_path.read_text(encoding="utf-8")
            status = json.loads((fundamentals / "fx_macro_provider_status.json").read_text(encoding="utf-8"))

            self.assertEqual(after, before)
            self.assertEqual(result["status"], "rate_limited")
            self.assertTrue(result["from_cache"])
            self.assertTrue(status["from_cache"])
            self.assertFalse((Path(tmp) / "outputs" / "sn_live_predictions.json").exists())
            self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()
