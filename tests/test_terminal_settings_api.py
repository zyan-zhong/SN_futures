from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api
from sn_futures.services.settings_service import get_terminal_settings_status


class TerminalSettingsApiTest(unittest.TestCase):
    def test_settings_status_is_available_without_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            os.environ.pop("SN_ALPHA_VANTAGE_KEY", None)
            os.environ.pop("SN_NEWSAPI_KEY", None)
            status, payload = handle_terminal_api("/api/terminal/settings/status", "GET", {}, None)
        self.assertEqual(status, 200)
        self.assertFalse(payload["alpha_vantage_configured"])
        self.assertFalse(payload["newsapi_configured"])
        self.assertIn("本机用户目录", payload["message_zh"])
        self.assertIn("user_data_dir", payload)
        self.assertIn("logs_dir", payload)
        self.assertIn("reports_dir", payload)
        self.assertIn("config_path", payload)
        self.assertIn("api_base_url", payload)
        self.assertIn("last_update_time", payload)

    def test_settings_secrets_save_returns_masked_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            os.environ.pop("SN_ALPHA_VANTAGE_KEY", None)
            os.environ.pop("SN_NEWSAPI_KEY", None)
            status, payload = handle_terminal_api(
                "/api/terminal/settings/secrets",
                "POST",
                {},
                {"SN_ALPHA_VANTAGE_KEY": "ALPHATEST123456", "SN_NEWSAPI_KEY": "NEWSTEST123456"},
            )
            secrets_file = Path(tmp) / "config" / "secrets.json"
            self.assertTrue(secrets_file.exists())
        self.assertEqual(status, 200)
        self.assertTrue(payload["alpha_vantage_configured"])
        self.assertTrue(payload["newsapi_configured"])
        self.assertNotIn("ALPHATEST123456", str(payload))
        self.assertNotIn("NEWSTEST123456", str(payload))
        self.assertIn("***", payload["alpha_vantage_masked"])
        self.assertIn("***", payload["newsapi_masked"])

    def test_local_api_provider_secret_save_returns_masked_canonical_status(self) -> None:
        token = "LOCAL_PROVIDER_TOKEN_1234567890"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            status, payload = handle_terminal_api(
                "/api/terminal/settings/secrets",
                "POST",
                {},
                {
                    "SN_LOCAL_API_PROVIDER_TOKEN": token,
                    "SN_LOCAL_API_PROVIDER_BASE_URL": "https://local-provider.example",
                    "SN_LOCAL_API_PROVIDER_ID": "custom_http_provider",
                    "SN_LOCAL_API_PROVIDER_ENABLED": "true",
                },
            )
            secrets_file = Path(tmp) / "config" / "secrets.json"
            saved = json.loads(secrets_file.read_text(encoding="utf-8"))

        self.assertEqual(status, 200)
        self.assertTrue(payload["local_api_provider_configured"])
        self.assertTrue(payload["local_api_provider_base_url_configured"])
        self.assertEqual(payload["local_api_provider_id"], "custom_http_provider")
        self.assertEqual(payload["local_api_provider_source"], "user_secrets")
        self.assertNotIn(token, json.dumps(payload, ensure_ascii=False))
        self.assertIn("***", payload["local_api_provider_token_masked"])
        self.assertEqual(saved["SN_LOCAL_API_PROVIDER_TOKEN"], token)
        self.assertNotIn("SN_MANAGED_DATA_PROXY_TOKEN", saved)

    def test_empty_secret_save_does_not_overwrite_existing_local_provider_token(self) -> None:
        token = "LOCAL_PROVIDER_TOKEN_1234567890"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            first_status, first_payload = handle_terminal_api(
                "/api/terminal/settings/secrets",
                "POST",
                {},
                {"SN_LOCAL_API_PROVIDER_TOKEN": token},
            )
            second_status, second_payload = handle_terminal_api(
                "/api/terminal/settings/secrets",
                "POST",
                {},
                {"SN_LOCAL_API_PROVIDER_TOKEN": ""},
            )

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertTrue(first_payload["local_api_provider_token_configured"])
        self.assertTrue(second_payload["local_api_provider_token_configured"])
        self.assertEqual(first_payload["local_api_provider_token_masked"], second_payload["local_api_provider_token_masked"])

    def test_legacy_managed_env_returns_deprecated_warning_without_secret_leak(self) -> None:
        token = "LEGACY_MANAGED_TOKEN_1234567890"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_MANAGED_DATA_PROXY_TOKEN": token, "SN_MANAGED_DATA_PROXY_URL": "https://legacy.example"},
            clear=True,
        ):
            payload = get_terminal_settings_status()

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertTrue(payload["local_api_provider_configured"])
        self.assertTrue(payload["local_api_provider_deprecated"])
        self.assertIn("SN_MANAGED_DATA_PROXY_TOKEN", payload["local_api_provider_deprecated_warnings"][0])
        self.assertNotIn(token, serialized)
        self.assertIn("***", payload["local_api_provider_token_masked"])

    def test_settings_secrets_rejects_authorization_and_raw_endpoint_secret_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            status, payload = handle_terminal_api(
                "/api/terminal/settings/secrets",
                "POST",
                {},
                {
                    "Authorization": "Bearer raw-secret-token-123456",
                    "endpoint_secret": "raw-secret-token-123456",
                },
            )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid_secret")
        self.assertNotIn("raw-secret-token-123456", json.dumps(payload, ensure_ascii=False))

    def test_settings_reset_does_not_delete_other_user_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            marker = Path(tmp) / "reports" / "keep.txt"
            marker.parent.mkdir(parents=True, exist_ok=True)
            marker.write_text("keep", encoding="utf-8")
            handle_terminal_api(
                "/api/terminal/settings/secrets",
                "POST",
                {},
                {"SN_ALPHA_VANTAGE_KEY": "ALPHATEST123456"},
            )
            status, payload = handle_terminal_api("/api/terminal/settings/reset", "POST", {}, {})
            self.assertTrue(marker.exists())
        self.assertEqual(status, 200)
        self.assertIn("其他用户数据未删除", payload["message_zh"])

    def test_short_key_is_rejected_with_chinese_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api(
                "/api/terminal/settings/secrets",
                "POST",
                {},
                {"SN_ALPHA_VANTAGE_KEY": "short"},
            )
        self.assertEqual(status, 400)
        self.assertIn("过短", payload["message"])

    def test_docs_include_settings_endpoints(self) -> None:
        endpoints = {item["path"] for item in TERMINAL_API_DOCS["endpoints"]}
        self.assertIn("/api/terminal/settings/status", endpoints)
        self.assertIn("/api/terminal/settings/secrets", endpoints)
        self.assertIn("/api/terminal/settings/reset", endpoints)

    def test_status_does_not_return_full_environment_key(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_ALPHA_VANTAGE_KEY": "ALPHATEST123456"},
            clear=False,
        ):
            payload = get_terminal_settings_status()
        self.assertNotIn("ALPHATEST123456", str(payload))
        self.assertIn("***", payload["alpha_vantage_masked"])


if __name__ == "__main__":
    unittest.main()
