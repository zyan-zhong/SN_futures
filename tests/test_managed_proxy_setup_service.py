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

from sn_futures.services.managed_proxy_setup_service import refresh_managed_proxy_setup, run_managed_proxy_schema_dry_run


class AuthFailedSetupClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        raise HTTPError(path, 401, "Unauthorized managed-secret-token", {}, None)


class TimeoutSetupClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        raise TimeoutError("timeout managed-secret-token")


class UnreachableSetupClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        raise URLError("unreachable managed-secret-token")


class NonJsonSetupClient:
    def get_json(self, path: str, headers: dict[str, str]) -> str:
        return "<html>not json</html>"


class EchoTokenSetupClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        return {"status": "ok", "echo": "managed-secret-token", "rows": []}


class MissingFieldsSetupClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        return {
            "status": "ok",
            "rows": [
                {
                    "symbol": "SN2606",
                    "feature_date": "2026-05-20",
                    "prediction_cutoff_date": "2026-05-20",
                    "source_timestamp": "2026-05-19T18:00:00",
                    "asof_date": "2026-05-19",
                    "ingest_timestamp": "2026-05-20T01:00:00",
                    "spot_price": 270000,
                }
            ],
        }


class PitLeakageSetupClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        row = complete_managed_row()
        row["source_timestamp"] = "2026-05-21T00:00:00"
        row["asof_date"] = "2026-05-21"
        return {"status": "ok", "rows": [row]}


class SuccessSetupClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        assert headers.get("Authorization") == "Bearer managed-secret-token"
        return {"status": "ok", "rows": [complete_managed_row()]}


def complete_managed_row() -> dict:
    return {
        "symbol": "SN2606",
        "feature_date": "2026-05-20",
        "trading_date": "2026-05-20",
        "prediction_cutoff_date": "2026-05-20",
        "source_timestamp": "2026-05-19T18:00:00",
        "asof_date": "2026-05-19",
        "ingest_timestamp": "2026-05-20T01:00:00",
        "spot_price": 270000,
        "spot_premium": 100,
        "spot_futures_basis": 80,
        "shfe_inventory": 12000,
        "shfe_warehouse_receipt": 2000,
        "lme_tin_close": 33000,
        "lme_inventory": 4500,
        "near_contract_close": 270100,
        "near_open_interest": 10000,
        "far_contract_close": 270800,
        "far_open_interest": 8000,
        "main_contract_switch_flag": 0,
    }


class ManagedProxySetupServiceTest(unittest.TestCase):
    def _env(self, tmp: str, **values: str) -> patch:
        base = {
            "SN_DATA_DIR": tmp,
            "SN_INSIGHT_DATA_DIR": "",
            "SN_MANAGED_PROXY_ENABLED": "",
            "SN_MANAGED_PROXY_BASE_URL": "",
            "SN_MANAGED_PROXY_TOKEN": "",
            "SN_MANAGED_PROXY_TIMEOUT_SECONDS": "",
            "SN_MANAGED_DATA_PROXY_ENABLED": "",
            "SN_MANAGED_DATA_PROXY_URL": "",
            "SN_MANAGED_DATA_PROXY_TOKEN": "",
        }
        base.update(values)
        return patch.dict(os.environ, base, clear=False)

    def test_disabled_setup_is_blocked_without_training_or_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            report = refresh_managed_proxy_setup()
            report_exists = Path(report["report_path"]).exists()

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["enabled"])
        self.assertFalse(report["configured"])
        self.assertFalse(report["managed_proxy_health_allowed"])
        self.assertFalse(report["pit_audit_allowed"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertEqual(report["endpoint_contract_status"], "not_run")
        self.assertEqual(report["next_allowed_action"], "enable_managed_proxy")
        self.assertIn("managed_proxy_disabled", report["blocking_reasons"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertNotIn("Authorization", serialized)
        self.assertTrue(report_exists)

    def test_enabled_without_base_url_points_to_base_url_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_PROXY_ENABLED="true",
            SN_MANAGED_PROXY_TOKEN="managed-secret-token",
        ):
            report = refresh_managed_proxy_setup()

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertEqual(report["status"], "blocked")
        self.assertTrue(report["enabled"])
        self.assertTrue(report["token_configured"])
        self.assertFalse(report["base_url_configured"])
        self.assertEqual(report["endpoint_contract_status"], "blocked")
        self.assertEqual(report["next_allowed_action"], "configure_managed_proxy_base_url")
        self.assertIn("managed_proxy_base_url_missing", report["blocking_reasons"])
        self.assertNotIn("managed-secret-token", serialized)
        self.assertIn("***", report["token_masked"])

    def test_enabled_without_token_points_to_token_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_PROXY_ENABLED="true",
            SN_MANAGED_PROXY_BASE_URL="https://managed.example",
        ):
            report = refresh_managed_proxy_setup()

        self.assertEqual(report["status"], "blocked")
        self.assertTrue(report["base_url_configured"])
        self.assertFalse(report["token_configured"])
        self.assertEqual(report["next_allowed_action"], "configure_managed_proxy_token")
        self.assertIn("managed_proxy_token_missing", report["blocking_reasons"])

    def test_user_local_config_file_is_supported_without_exposing_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            config_path = Path(tmp) / "config" / "managed_proxy.local.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            config_path.write_text(
                json.dumps(
                    {
                        "enabled": True,
                        "base_url": "https://managed.example",
                        "token": "managed-secret-token",
                        "timeout_seconds": 25,
                    }
                ),
                encoding="utf-8",
            )
            report = refresh_managed_proxy_setup()

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertTrue(report["enabled"])
        self.assertTrue(report["configured"])
        self.assertEqual(report["base_url_source"], "local_config")
        self.assertEqual(report["token_source"], "local_config")
        self.assertEqual(report["timeout_seconds"], 25)
        self.assertNotIn("managed-secret-token", serialized)

    def test_plain_http_non_local_and_invalid_timeout_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_PROXY_ENABLED="true",
            SN_MANAGED_PROXY_BASE_URL="http://managed.example",
            SN_MANAGED_PROXY_TOKEN="managed-secret-token",
            SN_MANAGED_PROXY_TIMEOUT_SECONDS="-5",
        ):
            report = refresh_managed_proxy_setup()

        self.assertEqual(report["endpoint_contract_status"], "blocked")
        self.assertIn("managed_proxy_https_required", report["blocking_reasons"])
        self.assertIn("managed_proxy_timeout_invalid", report["blocking_reasons"])

    def test_local_http_is_allowed_for_local_test_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_PROXY_ENABLED="true",
            SN_MANAGED_PROXY_BASE_URL="http://127.0.0.1:9999",
            SN_MANAGED_PROXY_TOKEN="managed-secret-token",
        ):
            report = refresh_managed_proxy_setup()

        self.assertEqual(report["endpoint_contract_status"], "pass")
        self.assertNotIn("managed_proxy_https_required", report["blocking_reasons"])

    def test_local_secret_files_are_ignored_and_templates_have_no_real_token(self) -> None:
        root = Path(__file__).resolve().parents[1]
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
        env_example = (root / ".env.example").read_text(encoding="utf-8")
        managed_example = (root / "config" / "managed_proxy.example.json").read_text(encoding="utf-8")

        self.assertIn(".env.local", gitignore)
        self.assertIn("config/managed_proxy.local.json", gitignore)
        self.assertIn("secrets/", gitignore)
        self.assertIn("SN_LOCAL_API_PROVIDER_BASE_URL", env_example)
        self.assertIn("SN_LOCAL_API_PROVIDER_TOKEN", env_example)
        self.assertNotIn("SN_MANAGED_PROXY_TOKEN=", env_example)
        self.assertIn("SN_MANAGED_PROXY_BASE_URL", managed_example)
        self.assertIn("deprecated", managed_example)
        self.assertNotIn("managed-secret-token", env_example + managed_example)

    def test_runtime_secret_scan_knows_managed_proxy_token_alias(self) -> None:
        root = Path(__file__).resolve().parents[1]
        scanner = (root / "scripts" / "scan_runtime_secrets.ps1").read_text(encoding="utf-8")

        self.assertIn("SN_MANAGED_PROXY_TOKEN", scanner)

    def test_dry_run_classifies_auth_timeout_unreachable_and_invalid_response(self) -> None:
        clients = [
            (AuthFailedSetupClient(), "auth_failed", "verify_managed_proxy_token"),
            (TimeoutSetupClient(), "endpoint_timeout", "fix_managed_proxy_endpoint_contract"),
            (UnreachableSetupClient(), "endpoint_unreachable", "fix_managed_proxy_endpoint_contract"),
            (NonJsonSetupClient(), "invalid_response_format", "fix_managed_proxy_endpoint_contract"),
        ]
        for client, reason, action in clients:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp, self._env(
                tmp,
                SN_MANAGED_PROXY_ENABLED="true",
                SN_MANAGED_PROXY_BASE_URL="https://managed.example",
                SN_MANAGED_PROXY_TOKEN="managed-secret-token",
            ):
                report = run_managed_proxy_schema_dry_run(client=client)

            serialized = json.dumps(report, ensure_ascii=False)
            self.assertEqual(report["status"], "blocked")
            self.assertIn(reason, report["blocking_reasons"])
            self.assertEqual(report["next_allowed_action"], action)
            self.assertNotIn("managed-secret-token", serialized)
            self.assertNotIn("Authorization", serialized)

    def test_dry_run_detects_token_echo_schema_missing_and_pit_leakage(self) -> None:
        cases = [
            (EchoTokenSetupClient(), "secret_leakage_detected", "blocked"),
            (MissingFieldsSetupClient(), "managed_proxy_schema_missing_fields", "blocked"),
            (PitLeakageSetupClient(), "managed_proxy_pit_leakage_failed", "blocked"),
        ]
        for client, reason, status in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp, self._env(
                tmp,
                SN_MANAGED_PROXY_ENABLED="true",
                SN_MANAGED_PROXY_BASE_URL="https://managed.example",
                SN_MANAGED_PROXY_TOKEN="managed-secret-token",
            ):
                report = run_managed_proxy_schema_dry_run(client=client)

            self.assertEqual(report["status"], status)
            self.assertIn(reason, report["blocking_reasons"])
            self.assertFalse(report["managed_proxy_health_allowed"])
            self.assertFalse(report["pit_audit_allowed"])
            self.assertFalse(report["feature_store_v12_allowed"])

    def test_success_fixture_with_all_required_fields_is_ready_for_health_and_pit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_PROXY_ENABLED="true",
            SN_MANAGED_PROXY_BASE_URL="https://managed.example",
            SN_MANAGED_PROXY_TOKEN="managed-secret-token",
        ):
            report = run_managed_proxy_schema_dry_run(client=SuccessSetupClient())
            output_text = Path(report["report_path"]).read_text(encoding="utf-8")

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["schema_contract_status"], "pass")
        self.assertEqual(report["pit_timestamp_contract_status"], "pass")
        self.assertEqual(report["missing_fields"], [])
        self.assertEqual(report["missing_timestamp_fields"], [])
        self.assertEqual(report["next_allowed_action"], "run_managed_proxy_health")
        self.assertTrue(report["managed_proxy_health_allowed"])
        self.assertTrue(report["pit_audit_allowed"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertNotIn("managed-secret-token", serialized)
        self.assertNotIn("managed-secret-token", output_text)


if __name__ == "__main__":
    unittest.main()
