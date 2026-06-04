from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.provider_smoke_test_service import run_provider_smoke_test


class FakeProviderClient:
    def fetch_minimal_sample(self, provider_id: str) -> dict[str, object]:
        return {
            "provider": provider_id,
            "fields": ["symbol", "close", "source_timestamp", "asof_date", "ingest_timestamp"],
            "rows": [{"symbol": "SN", "close": 1.0}],
            "freshness": "fresh",
        }


class ProviderSmokeServiceTest(unittest.TestCase):
    def test_missing_key_blocks_provider_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            payload = run_provider_smoke_test("twelvedata", write=False)

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["provider"], "twelvedata")
        self.assertFalse(payload["feature_store_v12_allowed"])
        self.assertFalse(payload["production_cache_written"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_configured_provider_minimal_smoke_does_not_build_v12_or_train(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_TWELVEDATA_API_KEY": "td-secret-key-123456"},
            clear=True,
        ):
            payload = run_provider_smoke_test("twelvedata", client=FakeProviderClient(), write=False)

        self.assertEqual(payload["status"], "pass")
        self.assertIn("close", payload["field_coverage"]["fields_seen"])
        self.assertFalse(payload["feature_store_v12_allowed"])
        self.assertFalse(payload["feature_store_written"])
        self.assertFalse(payload["production_cache_written"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_yfinance_smoke_is_research_only_and_never_unlocks_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            payload = run_provider_smoke_test("yfinance_research_only", client=FakeProviderClient(), write=False)

        self.assertEqual(payload["status"], "research_only")
        self.assertTrue(payload["research_only"])
        self.assertFalse(payload["production_eligible"])
        self.assertFalse(payload["realtime_guarantee"])
        self.assertFalse(payload["feature_store_v12_allowed"])


if __name__ == "__main__":
    unittest.main()
