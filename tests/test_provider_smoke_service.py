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
        self.assertIn("source_statuses", payload)
        self.assertIn("manifest", payload)
        self.assertEqual(payload["manifest"]["provider_id"], "twelvedata")
        self.assertIn("provider_key_missing", payload["manifest"]["blocking_reasons"])
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
        self.assertEqual(payload["manifest"]["provider_id"], "twelvedata")
        self.assertEqual(payload["manifest"]["row_count"], 1)
        self.assertEqual(payload["source_statuses"][0]["source_id"], "twelvedata")
        self.assertTrue(payload["source_statuses"][0]["success"])
        self.assertFalse(payload["feature_store_v12_allowed"])
        self.assertFalse(payload["feature_store_written"])
        self.assertFalse(payload["production_cache_written"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_configured_provider_with_no_rows_is_blocked_not_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_TWELVEDATA_API_KEY": "td-secret-key-123456"},
            clear=True,
        ):
            payload = run_provider_smoke_test("twelvedata", write=False)

        self.assertEqual(payload["status"], "blocked")
        self.assertIn("provider_smoke_no_rows", payload["blocking_reasons"])
        self.assertEqual(payload["manifest"]["row_count"], 0)
        self.assertFalse(payload["manifest"]["customer_prediction_generated"])

    def test_saved_local_api_provider_can_run_custom_provider_smoke_with_manifest(self) -> None:
        token = "LOCAL_PROVIDER_TOKEN_1234567890"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_LOCAL_API_PROVIDER_ENABLED": "true",
                "SN_LOCAL_API_PROVIDER_ID": "custom_http_provider",
                "SN_LOCAL_API_PROVIDER_BASE_URL": "https://local-provider.example",
                "SN_LOCAL_API_PROVIDER_TOKEN": token,
            },
            clear=True,
        ):
            payload = run_provider_smoke_test("custom_http_provider", client=FakeProviderClient(), write=False)

        self.assertEqual(payload["status"], "pass")
        self.assertEqual(payload["provider"], "custom_http_provider")
        self.assertEqual(payload["source_statuses"][0]["source_id"], "custom_http_provider")
        self.assertEqual(payload["source_statuses"][0]["row_count"], 1)
        self.assertEqual(payload["manifest"]["provider_id"], "custom_http_provider")
        self.assertEqual(payload["manifest"]["schema_version"], "local_api_provider_smoke_v1")
        self.assertEqual(payload["manifest"]["row_count"], 1)
        self.assertFalse(payload["manifest"]["sample_data_used"])
        self.assertFalse(payload["manifest"]["baseline_used"])
        self.assertFalse(payload["manifest"]["feature_store_written"])
        self.assertFalse(payload["manifest"]["training_invoked"])
        self.assertFalse(payload["manifest"]["backtest_invoked"])
        self.assertFalse(payload["manifest"]["customer_prediction_generated"])

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
