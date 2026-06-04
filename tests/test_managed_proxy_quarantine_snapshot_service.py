from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_proxy_endpoint_smoke_service import build_endpoint_smoke_report
from sn_futures.services.managed_proxy_quarantine_snapshot_service import (
    build_quarantine_snapshot_report,
    get_latest_quarantine_snapshot_report,
    pull_managed_proxy_quarantine_snapshot,
    redact_snapshot_preview,
    validate_quarantine_snapshot_preconditions,
    validate_snapshot_secret_safety,
    validate_snapshot_size_budget,
)


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
        "token_masked": "ma***en",
        "_base_url": "https://managed.example.test/private",
        "_token": "managed-secret-token",
        "timeout_seconds": 5,
    }
    payload.update(overrides)
    return payload


class FakeSnapshotClient:
    def __init__(self, rows: list[dict[str, object]] | None = None, error: Exception | None = None) -> None:
        self.rows = rows or []
        self.error = error
        self.calls: list[dict[str, object]] = []

    def get_quarantine_snapshot(self, path: str, headers: dict[str, str], requested_rows: int) -> dict[str, object]:
        self.calls.append({"path": path, "headers": dict(headers), "requested_rows": requested_rows})
        if self.error:
            raise self.error
        return {"status_code": 200, "content_type": "application/json", "body": {"rows": self.rows}}


class ManagedProxyQuarantineSnapshotServiceTest(unittest.TestCase):
    def test_smoke_missing_or_blocked_keeps_snapshot_blocked_without_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            missing = validate_quarantine_snapshot_preconditions()
            build_endpoint_smoke_report(
                status="blocked",
                auth_status="auth_failed",
                endpoint_reachable=True,
                response_format_status="not_run",
                token_echo_status="not_run",
                blocking_reasons=["auth_failed"],
                write=True,
            )
            blocked = pull_managed_proxy_quarantine_snapshot(config=_config(), client=FakeSnapshotClient([REQUIRED_ROW]))
            quarantine_root = Path(tmp) / "outputs" / "managed_proxy_quarantine"
            managed_cache = Path(tmp) / "outputs" / "fundamentals" / "managed_fundamentals.json"

        self.assertEqual(missing["status"], "blocked")
        self.assertIn("endpoint_smoke_report_missing", missing["blocking_reasons"])
        self.assertEqual(blocked["status"], "blocked")
        self.assertIn("auth_failed", blocked["blocking_reasons"])
        self.assertFalse(blocked["snapshot_pulled"])
        self.assertFalse(blocked["raw_rows_persisted"])
        self.assertFalse(blocked["managed_cache_updated"])
        self.assertFalse(blocked["feature_store_v12_allowed"])
        self.assertFalse(quarantine_root.exists())
        self.assertFalse(managed_cache.exists())

    def test_valid_small_snapshot_writes_quarantine_only_with_redacted_preview(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            build_endpoint_smoke_report(
                status="pass",
                auth_status="pass",
                endpoint_reachable=True,
                response_format_status="pass",
                token_echo_status="pass",
                schema_field_names_seen=list(REQUIRED_ROW),
                required_fields_present=["spot_price", "shfe_inventory"],
                timestamp_fields_present=["source_timestamp", "asof_date", "ingest_timestamp", "feature_date", "prediction_cutoff_date"],
                sample_row_count=1,
                write=True,
            )
            client = FakeSnapshotClient([REQUIRED_ROW])
            report = pull_managed_proxy_quarantine_snapshot(config=_config(), client=client, requested_rows=1, row_budget=3)
            quarantine_path = Path(str(report["quarantine_path"]))
            preview_path = Path(str(report["preview_path"]))
            managed_cache = Path(tmp) / "outputs" / "fundamentals" / "managed_fundamentals.json"
            feature_store = Path(tmp) / "outputs" / "feature_store"
            quarantine_path_exists = quarantine_path.exists()
            preview_path_exists = preview_path.exists()
            managed_cache_exists = managed_cache.exists()
            feature_store_exists = feature_store.exists()

        serialized_report = json.dumps(report, ensure_ascii=False)
        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["snapshot_pulled"])
        self.assertEqual(report["snapshot_row_count"], 1)
        self.assertTrue(quarantine_path_exists)
        self.assertTrue(preview_path_exists)
        self.assertIn("managed_proxy_quarantine", str(quarantine_path))
        self.assertFalse(managed_cache_exists)
        self.assertFalse(feature_store_exists)
        self.assertFalse(report["raw_rows_persisted"])
        self.assertFalse(report["managed_cache_updated"])
        self.assertFalse(report["production_eligible"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertIn("spot_price", report["schema_field_names_seen"])
        self.assertIn("source_timestamp", report["timestamp_fields_seen"])
        self.assertNotIn("managed-secret-token", serialized_report)
        self.assertNotIn("Authorization", serialized_report)
        self.assertNotIn("managed.example.test", serialized_report)
        self.assertNotIn("205000", serialized_report)

    def test_budget_too_large_response_too_large_and_token_echo_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            build_endpoint_smoke_report(
                status="pass",
                auth_status="pass",
                endpoint_reachable=True,
                response_format_status="pass",
                token_echo_status="pass",
                write=True,
            )
            requested_too_many = pull_managed_proxy_quarantine_snapshot(
                config=_config(),
                client=FakeSnapshotClient([REQUIRED_ROW]),
                requested_rows=6,
                row_budget=5,
            )
            response_too_large = pull_managed_proxy_quarantine_snapshot(
                config=_config(),
                client=FakeSnapshotClient([{**REQUIRED_ROW, "large_note": "x" * 500}]),
                requested_rows=1,
                row_budget=5,
                max_response_bytes=80,
            )
            token_echo = pull_managed_proxy_quarantine_snapshot(
                config=_config(),
                client=FakeSnapshotClient([{**REQUIRED_ROW, "provider_note": "managed-secret-token"}]),
                requested_rows=1,
                row_budget=5,
            )

        self.assertEqual(requested_too_many["status"], "blocked")
        self.assertIn("requested_rows_exceed_budget", requested_too_many["blocking_reasons"])
        self.assertEqual(response_too_large["status"], "blocked")
        self.assertIn("response_too_large", response_too_large["blocking_reasons"])
        self.assertEqual(token_echo["status"], "blocked")
        self.assertIn("secret_leakage_detected", token_echo["blocking_reasons"])
        self.assertFalse(token_echo["snapshot_pulled"])
        self.assertNotIn("managed-secret-token", json.dumps(token_echo, ensure_ascii=False))

    def test_preview_and_report_helpers_never_unlock_downstream_actions(self) -> None:
        preview = redact_snapshot_preview([REQUIRED_ROW])
        secret = validate_snapshot_secret_safety({"rows": [{**REQUIRED_ROW, "Authorization": "Bearer managed-secret-token"}]}, token="managed-secret-token", endpoint="https://managed.example.test")
        size = validate_snapshot_size_budget([REQUIRED_ROW], requested_rows=1, row_budget=5, max_response_bytes=100_000)
        report = build_quarantine_snapshot_report(
            status="ready",
            snapshot_pulled=True,
            snapshot_row_count=1,
            row_budget=5,
            redacted_preview=preview,
            schema_field_names_seen=list(REQUIRED_ROW),
            timestamp_fields_seen=["source_timestamp"],
            required_fields_seen=["spot_price"],
            write=False,
        )

        self.assertIn("field", json.dumps(preview, ensure_ascii=False))
        self.assertNotIn("205000", json.dumps(preview, ensure_ascii=False))
        self.assertEqual(secret["secret_safety_status"], "failed")
        self.assertEqual(size["status"], "pass")
        self.assertFalse(report["raw_rows_persisted"])
        self.assertFalse(report["managed_cache_updated"])
        self.assertFalse(report["production_eligible"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_latest_report_falls_back_to_blocked_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            latest = get_latest_quarantine_snapshot_report()

        self.assertEqual(latest["status"], "blocked")
        self.assertFalse(latest["snapshot_pulled"])
        self.assertIn("quarantine_snapshot_report_missing", latest["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
