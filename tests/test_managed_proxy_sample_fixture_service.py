from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_proxy_sample_fixture_service import (
    build_sample_fixture_contract_report,
    get_latest_sample_fixture_report,
    import_managed_proxy_sample_fixture,
    run_fixture_contract_tests,
    validate_sample_fixture_file,
)


def _valid_rows() -> list[dict[str, object]]:
    base = {
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
    second = dict(base)
    second.update(
        {
            "source_timestamp": "2024-01-03T15:00:00",
            "asof_date": "2024-01-03",
            "ingest_timestamp": "2024-01-03T18:00:00",
            "feature_date": "2024-01-04",
            "prediction_cutoff_date": "2024-01-04",
            "spot_price": 206000,
            "spot_futures_basis": 180,
            "shfe_inventory": 4900,
        }
    )
    return [base, second]


def _write_fixture(path: Path, payload: dict[str, object] | None = None) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload if payload is not None else {"fixture_only": True, "fixture_version": "test_v1", "rows": _valid_rows()}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return path


class ManagedProxySampleFixtureServiceTest(unittest.TestCase):
    def test_fixture_missing_fixture_only_marker_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            path = _write_fixture(Path(tmp) / "fixture.json", {"rows": _valid_rows()})
            result = validate_sample_fixture_file(path)

        self.assertEqual(result["status"], "rejected")
        self.assertIn("fixture_only_marker_missing", result["blocking_reasons"])
        self.assertFalse(result["feature_store_v12_allowed"])

    def test_fixture_with_token_or_authorization_header_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            path = _write_fixture(
                Path(tmp) / "fixture.json",
                {"fixture_only": True, "Authorization": "Bearer managed-secret-token", "rows": _valid_rows()},
            )
            result = validate_sample_fixture_file(path)
            serialized = json.dumps(result, ensure_ascii=False)

        self.assertEqual(result["status"], "rejected")
        self.assertIn("fixture_secret_like_value_detected", result["blocking_reasons"])
        self.assertNotIn("managed-secret-token", serialized)

    def test_missing_timestamps_or_required_fields_fail_contracts(self) -> None:
        rows = _valid_rows()
        rows[0].pop("source_timestamp")
        rows[1].pop("spot_price")
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            path = _write_fixture(Path(tmp) / "fixture.json", {"fixture_only": True, "rows": rows})
            report = run_fixture_contract_tests(path)

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["schema_contract_status"], "blocked")
        self.assertEqual(report["pit_replay_status"], "blocked")
        self.assertIn("missing_source_timestamp", report["blocking_reasons"])
        self.assertIn("canonical_required_fields_missing", report["blocking_reasons"])

    def test_pit_leakage_fails_contracts(self) -> None:
        rows = _valid_rows()
        rows[0]["source_timestamp"] = "2024-01-05T15:00:00"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            path = _write_fixture(Path(tmp) / "fixture.json", {"fixture_only": True, "rows": rows})
            report = run_fixture_contract_tests(path)

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["pit_replay_status"], "blocked")
        self.assertIn("source_timestamp_leakage", report["blocking_reasons"])
        self.assertFalse(report["feature_store_v12_allowed"])

    def test_quality_failures_do_not_unlock_v12(self) -> None:
        rows = _valid_rows()
        rows[0]["shfe_inventory"] = -1
        rows[1]["near_open_interest"] = -10
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            path = _write_fixture(Path(tmp) / "fixture.json", {"fixture_only": True, "rows": rows})
            report = run_fixture_contract_tests(path)

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["data_quality_status"], "blocked")
        self.assertIn("managed_data_quality:negative_inventory", report["blocking_reasons"])
        self.assertIn("managed_data_quality:impossible_open_interest", report["blocking_reasons"])
        self.assertFalse(report["feature_store_v12_allowed"])

    def test_valid_fixture_passes_contracts_but_remains_sample_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            path = _write_fixture(Path(tmp) / "fixture.json")
            report = run_fixture_contract_tests(path)
            latest = get_latest_sample_fixture_report()

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["row_count"], 2)
        self.assertEqual(report["schema_contract_status"], "ready")
        self.assertEqual(report["pit_replay_status"], "ready")
        self.assertEqual(report["data_quality_status"], "pass")
        self.assertTrue(report["sample_data_used"])
        self.assertFalse(report["managed_data_used"])
        self.assertFalse(report["production_eligible"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertEqual(latest["report_path"], report["report_path"])

    def test_import_does_not_write_real_managed_cache_or_change_setup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            path = _write_fixture(Path(tmp) / "fixture.json")
            report = import_managed_proxy_sample_fixture(path)
            managed_cache = Path(tmp) / "outputs" / "fundamentals" / "managed_fundamentals.json"
            setup_report = Path(tmp) / "outputs" / "diagnostics" / "managed_proxy_setup_report.json"

        self.assertEqual(report["status"], "ready")
        self.assertFalse(managed_cache.exists())
        self.assertFalse(setup_report.exists())
        self.assertFalse(report["feature_store_v12_allowed"])

    def test_build_report_with_no_fixture_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            report = build_sample_fixture_contract_report(fixture_path=Path(tmp) / "missing.json")

        self.assertEqual(report["status"], "blocked")
        self.assertIn("fixture_file_missing", report["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
