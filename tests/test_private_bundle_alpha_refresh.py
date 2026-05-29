from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.online_cross_market_service import refresh_online_cross_market_data


class FakeAlphaProvider:
    api_key = "FAKE_ALPHA_REFRESH_123456"

    def fetch_exchange_rate(self, **_: object) -> dict[str, object]:
        return {
            "success": True,
            "from_cache": False,
            "message": "ok",
            "data": {
                "Realtime Currency Exchange Rate": {
                    "5. Exchange Rate": "7.2000",
                    "6. Last Refreshed": "2026-05-29 12:00:00",
                }
            },
        }

    def fetch_fx_daily(self, **_: object) -> dict[str, object]:
        return {
            "success": True,
            "from_cache": False,
            "message": "ok",
            "data": {
                "Time Series FX (Daily)": {
                    "2026-05-28": {"4. close": "7.1000"},
                    "2026-05-29": {"4. close": "7.2000"},
                }
            },
        }

    def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
        return {
            "success": True,
            "from_cache": False,
            "message": "ok",
            "data": {"data": [{"date": "2026-05-29", "value": "4.35"}]},
        }

    def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
        return {
            "success": True,
            "from_cache": False,
            "message": "ok",
            "data": {"data": [{"date": "2026-05-01", "value": "10500"}]},
        }


class PrivateBundleAlphaRefreshTest(unittest.TestCase):
    def test_alpha_cross_market_refresh_writes_real_fields_without_lme_impersonation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = refresh_online_cross_market_data(provider=FakeAlphaProvider())  # type: ignore[arg-type]
            path = Path(tmp) / "outputs" / "fundamentals" / "sn_cross_market.json"
            status_path = Path(tmp) / "outputs" / "fundamentals" / "fx_macro_provider_status.json"
            payload = json.loads(path.read_text(encoding="utf-8"))
            status = json.loads(status_path.read_text(encoding="utf-8"))

        self.assertTrue(result["success"])
        self.assertEqual(status["status"], "success")
        rows = payload["rows"]
        self.assertTrue(any(row.get("usd_cny") for row in rows))
        self.assertTrue(any(row.get("us10y") for row in rows))
        self.assertTrue(any(row.get("copper_global_proxy") for row in rows))
        self.assertFalse(any(row.get("lme_tin_close") for row in rows))

    def test_terminal_cross_market_endpoint_routes_to_online_alpha_step(self) -> None:
        def fake_online_step(force: bool = False) -> dict[str, object]:
            return {
                "status": "success",
                "success": True,
                "message_zh": "online alpha fixture",
                "row_count": 2,
                "output_files": [],
                "force_seen": force,
            }

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.institutional_refresh_service.refresh_online_cross_market",
            side_effect=fake_online_step,
        ):
            code, payload = handle_terminal_api("/api/terminal/refresh/cross-market", "POST", body={"force": True})

        self.assertEqual(code, 200)
        steps = payload.get("steps", [])
        self.assertTrue(any(step.get("step_name") == "online_cross_market" and step.get("status") == "success" for step in steps))

    def test_rate_limit_does_not_overwrite_existing_cross_market_rows(self) -> None:
        class RateLimitProvider(FakeAlphaProvider):
            def fetch_exchange_rate(self, **_: object) -> dict[str, object]:
                return {"success": False, "from_cache": False, "message": "rate limit", "error_code": "rate_limited", "data": None}

            def fetch_fx_daily(self, **_: object) -> dict[str, object]:
                return self.fetch_exchange_rate()

            def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
                return self.fetch_exchange_rate()

            def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
                return self.fetch_exchange_rate()

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            data_path = fundamentals / "sn_cross_market.json"
            data_path.write_text(
                json.dumps({"rows": [{"trade_date": "2026-05-29", "usd_cny": 7.2, "us10y": 4.3}]}),
                encoding="utf-8",
            )
            result = refresh_online_cross_market_data(provider=RateLimitProvider())  # type: ignore[arg-type]
            payload = json.loads(data_path.read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "rate_limited")
        self.assertTrue(result["from_cache"])
        self.assertEqual(len(payload["rows"]), 1)
        self.assertEqual(payload["rows"][0]["usd_cny"], 7.2)


if __name__ == "__main__":
    unittest.main()
