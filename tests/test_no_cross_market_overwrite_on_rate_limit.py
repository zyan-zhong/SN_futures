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


class _InvalidKeyProvider:
    api_key = "test-key"

    def fetch_exchange_rate(self, **_: object) -> dict[str, object]:
        return {"success": False, "message": "Invalid API call. apikey=test-key"}

    def fetch_fx_daily(self, **_: object) -> dict[str, object]:
        return {"success": False, "message": "Invalid API call. apikey=test-key"}

    def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
        return {"success": False, "message": "Invalid API call. apikey=test-key"}

    def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
        return {"success": False, "message": "Invalid API call. apikey=test-key"}


class NoCrossMarketOverwriteOnRateLimitTest(unittest.TestCase):
    def test_failed_refresh_preserves_existing_rows_and_marks_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            data_path = fundamentals / "sn_cross_market.json"
            existing_rows = [
                {"trade_date": "2025-01-01", "usd_cny": 7.1, "us10y": 4.2},
                {"trade_date": "2025-01-02", "usd_cny": 7.2, "us10y": 4.3},
            ]
            data_path.write_text(json.dumps({"rows": existing_rows}, ensure_ascii=False), encoding="utf-8")

            result = refresh_online_cross_market_data(provider=_InvalidKeyProvider())
            payload = json.loads(data_path.read_text(encoding="utf-8"))

            self.assertEqual(payload["rows"], existing_rows)
            self.assertEqual(result["status"], "key_invalid")
            self.assertTrue(result["from_cache"])


if __name__ == "__main__":
    unittest.main()
