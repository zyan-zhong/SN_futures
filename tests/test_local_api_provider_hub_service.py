from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api
from sn_futures.services.provider_smoke_test_service import run_provider_smoke_test
from sn_futures.services.local_api_provider_hub_service import build_local_api_provider_hub
from sn_futures.services.terminal_service import build_terminal_data_status


class FakeProviderClient:
    def fetch_minimal_sample(self, provider_id: str) -> dict[str, object]:
        return {
            "provider": provider_id,
            "fields": ["symbol", "close", "source_timestamp", "asof_date", "ingest_timestamp"],
            "rows": [{"symbol": "SN", "close": 1.0}],
            "freshness": "fresh",
        }


class LocalApiProviderHubServiceTest(unittest.TestCase):
    def test_local_api_provider_mode_is_default_and_managed_proxy_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            payload = build_local_api_provider_hub(write=False)

        self.assertEqual(payload["provider_mode"], "local_api_provider")
        self.assertEqual(payload["current_step"], "configure_local_api_provider_credentials")
        self.assertEqual(payload["provider_credentials_status"], "missing_config")
        self.assertFalse(payload["managed_proxy_required"])
        self.assertFalse(payload["feature_store_v12_allowed"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_legacy_managed_proxy_vars_are_reported_as_legacy_not_default_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_MANAGED_PROXY_TOKEN": "legacy-proxy-secret-token"},
            clear=True,
        ):
            payload = build_local_api_provider_hub(write=False)

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertEqual(payload["provider_mode"], "local_api_provider")
        self.assertEqual(payload["legacy_managed_proxy_status"]["status"], "legacy_enterprise_proxy_detected")
        self.assertIn("legacy_managed_proxy_vars_detected", payload["warning_reasons"])
        self.assertNotIn("legacy-proxy-secret-token", serialized)

    def test_terminal_api_exposes_local_provider_hub(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/local-api-provider/hub", paths)
        self.assertIn("/api/terminal/local-api-provider/credentials", paths)
        self.assertIn("/api/terminal/local-api-provider/smoke", paths)

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            status, payload = handle_terminal_api("/api/terminal/local-api-provider/hub", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["provider_mode"], "local_api_provider")
        self.assertEqual(payload["current_step"], "configure_local_api_provider_credentials")

    def test_provider_smoke_result_updates_data_status_local_flow(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_LOCAL_API_PROVIDER_ENABLED": "true",
                "SN_LOCAL_API_PROVIDER_ID": "custom_http_provider",
                "SN_LOCAL_API_PROVIDER_BASE_URL": "https://local-provider.example",
                "SN_LOCAL_API_PROVIDER_TOKEN": "LOCAL_PROVIDER_TOKEN_1234567890",
            },
            clear=True,
        ):
            smoke = run_provider_smoke_test("custom_http_provider", client=FakeProviderClient(), write=True)
            payload = build_terminal_data_status()

        self.assertEqual(smoke["status"], "pass")
        local_flow = payload["local_api_provider_flow"]
        self.assertEqual(local_flow["provider_smoke_status"], "pass")
        self.assertEqual(local_flow["provider_smoke"]["manifest"]["provider_id"], "custom_http_provider")
        self.assertEqual(local_flow["next_allowed_action"], "safe_refresh_data_status")
        self.assertTrue(local_flow["safe_refresh_available"])
        self.assertFalse(local_flow["feature_store_written"])
        self.assertFalse(local_flow["training_invoked"])
        self.assertFalse(local_flow["backtest_invoked"])
        self.assertFalse(local_flow["customer_prediction_generated"])

    def test_run_smoke_endpoint_rejects_raw_authorization_or_token_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            status, payload = handle_terminal_api(
                "/api/terminal/local-api-provider/run-smoke",
                "POST",
                {},
                {"provider_id": "custom_http_provider", "Authorization": "Bearer raw-secret-token-123456"},
            )

        self.assertEqual(status, 400)
        self.assertIn("raw_provider_credential_input_forbidden", payload["blocking_reasons"])
        self.assertNotIn("raw-secret-token-123456", json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
