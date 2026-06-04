from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError, URLError

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS
from sn_futures.services.managed_proxy_health_service import check_managed_proxy_health, get_managed_proxy_health


class AuthFailedClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        raise HTTPError(path, 401, "Unauthorized token=managed-secret-token", {}, None)


class UnreachableClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        raise URLError("endpoint unreachable token=managed-secret-token")


class MissingSchemaClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        return {
            "status": "success",
            "rows": [
                {
                    "trade_date": "2026-05-20",
                    "symbol": "SN2606",
                    "spot_price": 270000,
                }
            ],
        }


class RequiredFieldsClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        assert path.startswith("/api/sn/fundamentals/history?")
        assert headers.get("X-SN-License-Token") == "managed-secret-token"
        row = {
            "trade_date": "2026-05-20",
            "symbol": "SN2606",
            "near_contract": "SN2606",
            "far_contract": "SN2607",
            "main_contract": "SN2606",
        }
        for field in MANAGED_REQUIRED_RESEARCH_FIELDS:
            row[field] = 1.0
        return {"status": "success", "rows": [row]}


class ManagedProxyHealthServiceTest(unittest.TestCase):
    def _env(self, tmp: str, **values: str) -> patch:
        base = {
            "SN_DATA_DIR": tmp,
            "SN_INSIGHT_DATA_DIR": "",
            "SN_MANAGED_DATA_PROXY_TOKEN": "",
            "SN_MANAGED_DATA_PROXY_URL": "",
            "SN_MANAGED_DATA_PROXY_ENABLED": "",
        }
        base.update(values)
        return patch.dict(os.environ, base, clear=False)

    def test_disabled_returns_blocked_without_secret_or_fake_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            health = get_managed_proxy_health()

        self.assertEqual(health["provider_status"], "disabled")
        self.assertEqual(health["status"], "blocked")
        self.assertFalse(health["enabled"])
        self.assertFalse(health["configured"])
        self.assertIn("managed_proxy_disabled", health["blocking_reasons"])
        self.assertFalse(health["v12_allowed"])
        self.assertTrue(health["no_fake_data"])

    def test_enabled_without_token_is_token_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp, SN_MANAGED_DATA_PROXY_ENABLED="1", SN_MANAGED_DATA_PROXY_URL="https://managed.example"):
            health = get_managed_proxy_health()

        self.assertEqual(health["provider_status"], "token_missing")
        self.assertIn("managed_proxy_token_missing", health["blocking_reasons"])
        self.assertFalse(health["v12_allowed"])

    def test_new_managed_proxy_env_aliases_are_supported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_PROXY_ENABLED="true",
            SN_MANAGED_PROXY_BASE_URL="https://managed.example",
            SN_MANAGED_PROXY_TOKEN="managed-secret-token",
        ):
            health = get_managed_proxy_health()

        serialized = json.dumps(health, ensure_ascii=False)
        self.assertTrue(health["enabled"])
        self.assertTrue(health["configured"])
        self.assertTrue(health["token_configured"])
        self.assertTrue(health["endpoint_configured"])
        self.assertNotIn("managed-secret-token", serialized)

    def test_token_without_endpoint_is_base_url_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp, SN_MANAGED_DATA_PROXY_TOKEN="managed-secret-token"):
            health = get_managed_proxy_health()

        self.assertEqual(health["provider_status"], "base_url_missing")
        self.assertTrue(health["token_configured"])
        self.assertFalse(health["endpoint_configured"])
        self.assertIn("managed_proxy_base_url_missing", health["blocking_reasons"])

    def test_auth_failed_401_is_classified_and_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_DATA_PROXY_TOKEN="managed-secret-token",
            SN_MANAGED_DATA_PROXY_URL="https://managed.example",
        ):
            health = check_managed_proxy_health(client=AuthFailedClient())

        serialized = json.dumps(health, ensure_ascii=False)
        self.assertEqual(health["provider_status"], "auth_failed")
        self.assertIn("managed_proxy_auth_failed", health["blocking_reasons"])
        self.assertNotIn("managed-secret-token", serialized)
        self.assertFalse(health["v12_allowed"])

    def test_unreachable_endpoint_is_classified_and_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_DATA_PROXY_TOKEN="managed-secret-token",
            SN_MANAGED_DATA_PROXY_URL="https://managed.example",
        ):
            health = check_managed_proxy_health(client=UnreachableClient())

        serialized = json.dumps(health, ensure_ascii=False)
        self.assertEqual(health["provider_status"], "endpoint_unreachable")
        self.assertIn("managed_proxy_endpoint_unreachable", health["blocking_reasons"])
        self.assertNotIn("managed-secret-token", serialized)

    def test_schema_missing_fields_blocks_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_DATA_PROXY_TOKEN="managed-secret-token",
            SN_MANAGED_DATA_PROXY_URL="https://managed.example",
        ):
            health = check_managed_proxy_health(client=MissingSchemaClient())

        self.assertEqual(health["provider_status"], "schema_missing_fields")
        self.assertIn("managed_proxy_schema_missing_fields", health["blocking_reasons"])
        self.assertIn("shfe_warehouse_receipt", health["missing_fields"])
        self.assertFalse(health["v12_allowed"])

    def test_success_with_required_fields_allows_v12_without_secret_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_DATA_PROXY_TOKEN="managed-secret-token",
            SN_MANAGED_DATA_PROXY_URL="https://managed.example",
        ):
            health = check_managed_proxy_health(client=RequiredFieldsClient())
            output_path = Path(health["output_path"])
            output_exists = output_path.exists()
            output_text = output_path.read_text(encoding="utf-8")

        serialized = json.dumps(health, ensure_ascii=False)
        self.assertEqual(health["provider_status"], "success_with_required_fields")
        self.assertEqual(health["status"], "ready")
        self.assertEqual(health["missing_fields"], [])
        self.assertTrue(health["v12_allowed"])
        self.assertTrue(output_exists)
        self.assertNotIn("managed-secret-token", serialized)
        self.assertNotIn("managed-secret-token", output_text)
        self.assertFalse(health["active_model_written"])
        self.assertFalse(health["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
