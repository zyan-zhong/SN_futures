from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_proxy_endpoint_smoke_service import (
    build_endpoint_smoke_report,
    detect_token_echo_in_response,
    get_latest_endpoint_smoke_report,
    run_endpoint_smoke_test,
    validate_auth_without_persisting_rows,
    validate_pit_timestamps_from_redacted_sample,
    validate_schema_from_redacted_sample,
)
from sn_futures.services.research_decision_board_service import build_research_decision_board


REQUIRED_ROW = {
    "source_timestamp": "2024-01-02T15:00:00",
    "asof_date": "2024-01-02",
    "ingest_timestamp": "2024-01-02T18:00:00",
    "feature_date": "2024-01-03",
    "prediction_cutoff_date": "2024-01-03",
    "spot_price": 205000,
    "spot_premium": 150,
    "spot_futures_basis": 120,
    "shfe_inventory": 4800,
    "shfe_warehouse_receipt": 3500,
    "lme_tin_close": 25200,
    "lme_inventory": 4100,
    "near_contract_close": 204880,
    "near_open_interest": 11000,
    "far_contract_close": 205300,
    "far_open_interest": 8700,
    "main_contract_switch_flag": 0,
}


def _config(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "enabled": True,
        "configured": True,
        "base_url_configured": True,
        "token_configured": True,
        "token_masked": "sm***en",
        "_base_url": "https://managed.example.test",
        "_token": "managed-secret-token",
        "timeout_seconds": 5,
    }
    payload.update(overrides)
    return payload


class FakeSmokeClient:
    def __init__(self, result: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.result = result or {}
        self.error = error

    def get_smoke(self, path: str, headers: dict[str, str]) -> dict[str, object]:
        if self.error:
            raise self.error
        return dict(self.result)


class ManagedProxyEndpointSmokeServiceTest(unittest.TestCase):
    def test_disabled_or_missing_config_is_blocked_without_endpoint_call(self) -> None:
        disabled = run_endpoint_smoke_test(config=_config(enabled=False, configured=False), client=FakeSmokeClient(), write=False)
        missing = run_endpoint_smoke_test(
            config=_config(configured=False, base_url_configured=False, token_configured=False, _base_url="", _token=""),
            client=FakeSmokeClient(),
            write=False,
        )

        self.assertEqual(disabled["status"], "blocked")
        self.assertEqual(disabled["auth_status"], "not_run")
        self.assertFalse(disabled["endpoint_reachable"])
        self.assertIn("managed_proxy_disabled", disabled["blocking_reasons"])
        self.assertEqual(missing["status"], "blocked")
        self.assertIn("managed_proxy_base_url_missing", missing["blocking_reasons"])
        self.assertIn("managed_proxy_token_missing", missing["blocking_reasons"])

    def test_auth_timeout_non_json_and_token_echo_are_classified(self) -> None:
        auth = run_endpoint_smoke_test(config=_config(), client=FakeSmokeClient({"status_code": 401, "content_type": "application/json"}), write=False)
        timeout = run_endpoint_smoke_test(config=_config(), client=FakeSmokeClient(error=TimeoutError("slow endpoint")), write=False)
        non_json = run_endpoint_smoke_test(config=_config(), client=FakeSmokeClient({"status_code": 200, "content_type": "text/plain", "body": "ok"}), write=False)
        echoed = run_endpoint_smoke_test(
            config=_config(),
            client=FakeSmokeClient({"status_code": 200, "content_type": "application/json", "body": {"rows": [REQUIRED_ROW], "echo": "managed-secret-token"}}),
            write=False,
        )
        http_auth = run_endpoint_smoke_test(
            config=_config(),
            client=FakeSmokeClient(error=HTTPError("https://managed.example.test", 403, "Forbidden", hdrs=None, fp=None)),
            write=False,
        )

        self.assertEqual(auth["auth_status"], "auth_failed")
        self.assertEqual(timeout["status"], "blocked")
        self.assertIn("endpoint_timeout", timeout["blocking_reasons"])
        self.assertEqual(non_json["response_format_status"], "invalid_response_format")
        self.assertEqual(echoed["token_echo_status"], "secret_leakage_detected")
        self.assertNotIn("managed-secret-token", json.dumps(echoed, ensure_ascii=False))
        self.assertEqual(http_auth["auth_status"], "auth_failed")

    def test_valid_response_passes_without_persisting_raw_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = run_endpoint_smoke_test(
                config=_config(),
                client=FakeSmokeClient({"status_code": 200, "content_type": "application/json", "body": {"rows": [REQUIRED_ROW]}}),
            )
            latest = get_latest_endpoint_smoke_report()
            managed_cache = Path(tmp) / "outputs" / "fundamentals" / "managed_fundamentals.json"

        serialized = json.dumps(result, ensure_ascii=False)
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["auth_status"], "pass")
        self.assertTrue(result["endpoint_reachable"])
        self.assertEqual(result["sample_row_count"], 1)
        self.assertGreater(len(result["schema_field_names_seen"]), 0)
        self.assertIn("source_timestamp", result["timestamp_fields_present"])
        self.assertFalse(result["raw_rows_persisted"])
        self.assertFalse(result["managed_data_cache_updated"])
        self.assertFalse(result["feature_store_v12_allowed"])
        self.assertFalse(managed_cache.exists())
        self.assertEqual(latest["report_path"], result["report_path"])
        self.assertNotIn("205000", serialized)
        self.assertNotIn("managed-secret-token", serialized)

    def test_validation_helpers_use_redacted_field_names_only(self) -> None:
        schema = validate_schema_from_redacted_sample([REQUIRED_ROW])
        pit = validate_pit_timestamps_from_redacted_sample([REQUIRED_ROW])
        auth = validate_auth_without_persisting_rows({"status_code": 200, "content_type": "application/json"})
        echo = detect_token_echo_in_response({"token": "managed-secret-token"}, "managed-secret-token")

        self.assertEqual(schema["status"], "pass")
        self.assertIn("spot_price", schema["required_fields_present"])
        self.assertEqual(pit["status"], "pass")
        self.assertEqual(auth["auth_status"], "pass")
        self.assertEqual(echo["token_echo_status"], "secret_leakage_detected")

    def test_build_report_does_not_allow_v12_or_downstream_side_effects(self) -> None:
        report = build_endpoint_smoke_report(status="pass", auth_status="pass", endpoint_reachable=True, schema_field_names_seen=["spot_price"])

        self.assertFalse(report["raw_rows_persisted"])
        self.assertFalse(report["managed_data_cache_updated"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_decision_board_after_smoke_pass_points_to_health_not_v12_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            diagnostics = out / "diagnostics"
            diagnostics.mkdir(parents=True)
            (diagnostics / "managed_proxy_config_wizard_report.json").write_text(json.dumps({"status": "ready"}), encoding="utf-8")
            (diagnostics / "managed_proxy_setup_report.json").write_text(
                json.dumps({"status": "ready", "managed_proxy_health_allowed": True, "next_allowed_action": "run_managed_proxy_health"}),
                encoding="utf-8",
            )
            run_endpoint_smoke_test(
                config=_config(),
                client=FakeSmokeClient({"status_code": 200, "content_type": "application/json", "body": {"rows": [REQUIRED_ROW]}}),
            )
            board = build_research_decision_board()

        self.assertEqual(board["managed_proxy_summary"]["endpoint_smoke_status"], "pass")
        self.assertEqual(board["managed_proxy_summary"]["endpoint_smoke_next_allowed_action"], "run_managed_proxy_health")
        self.assertEqual(board["next_allowed_action"], "run_managed_proxy_health")
        self.assertFalse(board["training_dataset_v12_allowed"])
        self.assertFalse(board["candidate_training_allowed"])


if __name__ == "__main__":
    unittest.main()
