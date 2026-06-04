from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_data_audit_service import (
    build_managed_audit_manifest,
    detect_timestamp_leakage,
    summarize_managed_field_lag,
    validate_managed_point_in_time_rows,
)
from sn_futures.services.managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS


def _complete_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "trade_date": "2026-05-20",
        "feature_date": "2026-05-20",
        "prediction_cutoff_date": "2026-05-20",
        "source_timestamp": "2026-05-19T18:00:00",
        "asof_date": "2026-05-19",
        "ingest_timestamp": "2026-05-21T09:30:00",
        "symbol": "SN2606",
    }
    for field in MANAGED_REQUIRED_RESEARCH_FIELDS:
        row[field] = 1.0
    row.update(overrides)
    return row


class ManagedDataAuditServiceTest(unittest.TestCase):
    def test_disabled_managed_proxy_writes_blocked_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_MANAGED_DATA_PROXY_TOKEN": "",
                "SN_MANAGED_DATA_PROXY_URL": "",
                "SN_MANAGED_DATA_PROXY_ENABLED": "",
            },
            clear=False,
        ):
            manifest = build_managed_audit_manifest()
            manifest_text = Path(manifest["manifest_path"]).read_text(encoding="utf-8")

        self.assertEqual(manifest["status"], "blocked")
        self.assertEqual(manifest["managed_proxy_status"]["provider_status"], "disabled")
        self.assertIn("managed_proxy_disabled", manifest["blocking_reasons"])
        self.assertFalse(manifest["managed_data_used"])
        self.assertFalse(manifest["fake_data_used"])
        self.assertFalse(manifest["training_invoked"])
        self.assertFalse(manifest["active_updated"])
        self.assertFalse(manifest["customer_prediction_generated"])
        self.assertIn('"audit_version"', manifest_text)

    def test_endpoint_or_token_missing_blocks_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_MANAGED_DATA_PROXY_ENABLED": "1",
                "SN_MANAGED_DATA_PROXY_URL": "https://managed.example",
                "SN_MANAGED_DATA_PROXY_TOKEN": "",
            },
            clear=False,
        ):
            token_missing = build_managed_audit_manifest()

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_MANAGED_DATA_PROXY_ENABLED": "1",
                "SN_MANAGED_DATA_PROXY_URL": "",
                "SN_MANAGED_DATA_PROXY_TOKEN": "managed-secret-token",
            },
            clear=False,
        ):
            endpoint_missing = build_managed_audit_manifest()

        self.assertEqual(token_missing["status"], "blocked")
        self.assertIn("managed_proxy_token_missing", token_missing["blocking_reasons"])
        self.assertEqual(endpoint_missing["status"], "blocked")
        self.assertIn("managed_proxy_base_url_missing", endpoint_missing["blocking_reasons"])

    def test_missing_required_timestamp_fields_are_blocked(self) -> None:
        base = _complete_row()
        cases = {
            "source_timestamp": "missing_source_timestamp",
            "asof_date": "missing_asof_date",
            "ingest_timestamp": "missing_ingest_timestamp",
        }

        for field, reason in cases.items():
            row = dict(base)
            row.pop(field)
            with self.subTest(field=field):
                result = validate_managed_point_in_time_rows([row])
                self.assertEqual(result["status"], "blocked")
                self.assertIn(field, result["missing_timestamp_fields"])
                self.assertIn(reason, result["blocking_reasons"])

    def test_report_date_without_asof_date_is_not_accepted_as_point_in_time(self) -> None:
        row = _complete_row(report_date="2026-05-19")
        row.pop("asof_date")

        result = validate_managed_point_in_time_rows([row])

        self.assertEqual(result["status"], "blocked")
        self.assertIn("asof_date", result["missing_timestamp_fields"])
        self.assertIn("missing_asof_date", result["blocking_reasons"])

    def test_asof_and_source_timestamp_leakage_fail(self) -> None:
        asof_late = validate_managed_point_in_time_rows([_complete_row(asof_date="2026-05-21")])
        source_late = validate_managed_point_in_time_rows([_complete_row(source_timestamp="2026-05-21T08:00:00")])
        detected = detect_timestamp_leakage([_complete_row(asof_date="2026-05-21", source_timestamp="2026-05-21T08:00:00")])

        self.assertFalse(asof_late["leakage_checks"]["asof_date_leakage_pass"])
        self.assertFalse(source_late["leakage_checks"]["source_timestamp_leakage_pass"])
        self.assertFalse(detected["asof_date_leakage_pass"])
        self.assertFalse(detected["source_timestamp_leakage_pass"])

    def test_ingest_timestamp_can_be_later_but_not_used_as_asof(self) -> None:
        result = validate_managed_point_in_time_rows([_complete_row(ingest_timestamp="2026-06-01T12:00:00")])

        self.assertEqual(result["status"], "pass")
        self.assertTrue(result["leakage_checks"]["ingest_timestamp_not_used_as_asof_pass"])
        self.assertTrue(result["leakage_checks"]["point_in_time_join_ready"])

    def test_lag_summary_reports_negative_and_missing_lags(self) -> None:
        summary = summarize_managed_field_lag(
            [
                _complete_row(asof_date="2026-05-19"),
                _complete_row(asof_date="2026-05-21"),
                _complete_row(asof_date=""),
            ]
        )

        self.assertEqual(summary["rows_with_negative_lag"], 1)
        self.assertEqual(summary["rows_with_missing_lag"], 1)
        self.assertIn("spot_price", summary["by_field"])
        self.assertIn("median_lag_days", summary)

    def test_manifest_does_not_include_full_token_or_authorization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_MANAGED_DATA_PROXY_TOKEN": "managed-secret-token",
                "SN_MANAGED_DATA_PROXY_URL": "https://managed.example/secret-token",
            },
            clear=False,
        ):
            out = Path(tmp) / "outputs" / "fundamentals"
            out.mkdir(parents=True, exist_ok=True)
            (out / "managed_fundamentals.json").write_text(json.dumps({"rows": [_complete_row()]}), encoding="utf-8")
            manifest = build_managed_audit_manifest()
            text = Path(manifest["manifest_path"]).read_text(encoding="utf-8")

        serialized = json.dumps(manifest, ensure_ascii=False)
        self.assertNotIn("managed-secret-token", serialized)
        self.assertNotIn("managed-secret-token", text)
        self.assertNotIn("Authorization", serialized)
        self.assertNotIn("secret-token", serialized)
        self.assertIs(manifest["managed_proxy_status"]["token_configured"], True)
        self.assertEqual(manifest["managed_proxy_status"]["token_masked"], "ma***en")


if __name__ == "__main__":
    unittest.main()
