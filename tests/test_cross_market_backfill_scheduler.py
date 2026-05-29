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


class RecordingAlphaProvider:
    api_key = "TEST_ALPHA_BACKFILL"

    def __init__(self) -> None:
        self.calls: list[str] = []

    def fetch_fx_daily(self, **_: object) -> dict[str, object]:
        self.calls.append("fx_daily")
        return {
            "success": True,
            "from_cache": False,
            "message": "ok",
            "data": {"Time Series FX (Daily)": {"2026-05-25": {"4. close": "7.12"}}},
        }

    def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
        self.calls.append("treasury_yield")
        return {"success": True, "from_cache": False, "message": "ok", "data": {"data": [{"date": "2026-05-25", "value": "4.2"}]}}

    def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
        self.calls.append("copper")
        return {"success": True, "from_cache": False, "message": "ok", "data": {"data": [{"date": "2026-05-01", "value": "9700"}]}}


class CrossMarketBackfillSchedulerTest(unittest.TestCase):
    def test_backfill_limits_endpoint_count_per_run_and_records_history(self) -> None:
        provider = RecordingAlphaProvider()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = refresh_cross_market_backfill(provider=provider, max_endpoints_per_run=1)
            history_path = Path(tmp) / "outputs" / "fundamentals" / "alpha_attempt_history.json"
            history = json.loads(history_path.read_text(encoding="utf-8"))

        self.assertEqual(len(provider.calls), 1)
        self.assertEqual(result["attempted_endpoint_count"], 1)
        self.assertGreaterEqual(len(history.get("attempts", [])), 1)
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse(result["active_model_written"])


if __name__ == "__main__":
    unittest.main()
