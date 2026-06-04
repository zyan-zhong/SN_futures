from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v12_input_contract_service import (
    build_v12_input_contract_report,
    compare_production_cache_against_v12_requirements,
)


REQUIRED_FIELDS = {
    "spot_price": 210100.0,
    "spot_premium": 120.0,
    "spot_futures_basis": 80.0,
    "shfe_inventory": 3000.0,
    "shfe_warehouse_receipt": 500.0,
    "lme_tin_close": 33000.0,
    "lme_inventory": 4900.0,
    "near_contract_close": 209900.0,
    "near_open_interest": 11000.0,
    "far_contract_close": 210700.0,
    "far_open_interest": 9000.0,
    "main_contract_switch_flag": 0.0,
}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _row(feature_date: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "feature_date": feature_date,
        "trading_date": feature_date,
        "prediction_cutoff_date": feature_date,
        "source_timestamp": f"{feature_date}T09:00:00",
        "asof_date": feature_date,
        "ingest_timestamp": f"{feature_date}T18:00:00",
        **REQUIRED_FIELDS,
    }
    row.update(overrides)
    return row


def _seed_ready_inputs(tmp: str, rows: list[dict[str, object]] | None = None) -> None:
    out = Path(tmp) / "outputs"
    diagnostics = out / "diagnostics"
    rows = rows or [_row("2026-01-03"), _row("2026-01-04")]
    _write_json(out / "fundamentals" / "managed_fundamentals.json", {"status": "success", "rows": rows})
    _write_json(
        diagnostics / "managed_data_production_cache_gate_report.json",
        {
            "status": "ready",
            "production_cache_write_allowed": True,
            "production_cache_written": True,
            "feature_store_v12_allowed": True,
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_data_backfill_planner_report.json",
        {
            "status": "ready",
            "required_date_range": {"date_start": "2026-01-03", "date_end": "2026-01-04"},
            "coverage_budget": {
                "min_row_count": 2,
                "min_date_coverage_ratio": 1.0,
                "max_missing_rate_by_required_field": {field: 0.0 for field in REQUIRED_FIELDS},
                "min_timestamp_coverage": 1.0,
                "min_pit_replay_pass_rate": 1.0,
                "min_quality_score": 0.9,
                "allowed_duplicate_key_count": 0,
            },
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_pit_replay_report.json",
        {"status": "ready", "point_in_time_join_ready": True, "cases_passed": 2, "cases_failed": 0, "blocking_reasons": []},
    )
    _write_json(
        diagnostics / "managed_data_audit_manifest.json",
        {
            "status": "ready",
            "v12_allowed": True,
            "leakage_checks": {
                "source_timestamp_leakage_pass": True,
                "asof_date_leakage_pass": True,
                "feature_date_cutoff_pass": True,
                "ingest_timestamp_not_used_as_asof_pass": True,
                "point_in_time_join_ready": True,
            },
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_data_quality_scorecard.json",
        {"status": "pass", "gate_passed": True, "quality_score": 0.98, "blocking_reasons": []},
    )


class FeatureStoreV12InputContractServiceTest(unittest.TestCase):
    def test_no_production_cache_blocks_contract_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.feature_store_v12_input_contract_service.build_feature_store_v12"
        ) as build_v12:
            report = build_v12_input_contract_report()
            feature_store_v12 = Path(tmp) / "outputs" / "feature_store" / "v12" / "feature_store.csv"
            active_model = Path(tmp) / "outputs" / "model_registry" / "active_model.json"

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["input_contract_ready"])
        self.assertFalse(report["feature_store_v12_build_allowed"])
        self.assertIn("production_cache_missing", report["blocking_reasons"])
        self.assertFalse(feature_store_v12.exists())
        self.assertFalse(active_model.exists())
        build_v12.assert_not_called()

    def test_production_cache_gate_blocked_blocks_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _seed_ready_inputs(tmp)
            _write_json(
                Path(tmp) / "outputs" / "diagnostics" / "managed_data_production_cache_gate_report.json",
                {"status": "blocked", "production_cache_written": False, "feature_store_v12_allowed": False, "blocking_reasons": ["manual_approval_missing"]},
            )
            report = build_v12_input_contract_report()

        self.assertEqual(report["status"], "blocked")
        self.assertIn("production_cache_gate_blocked", report["blocking_reasons"])

    def test_missing_fields_timestamps_date_range_coverage_pit_and_quality_fail(self) -> None:
        cases = [
            ("missing_required_fields", [_row("2026-01-03", spot_price="")], "missing_required_fields"),
            ("missing_timestamp_fields", [_row("2026-01-03", source_timestamp="")], "missing_timestamp_fields"),
            ("date_range_insufficient", [_row("2026-01-03")], "date_range_insufficient"),
            ("coverage_below_budget", [_row("2026-01-03"), _row("2026-01-04", spot_premium="")], "coverage_below_budget"),
        ]
        for _, rows, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
                _seed_ready_inputs(tmp, rows=rows)
                report = build_v12_input_contract_report()
            self.assertEqual(report["status"], "blocked")
            self.assertIn(reason, report["blocking_reasons"])

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _seed_ready_inputs(tmp)
            _write_json(Path(tmp) / "outputs" / "diagnostics" / "managed_data_audit_manifest.json", {"status": "blocked", "v12_allowed": False})
            pit = build_v12_input_contract_report()
        self.assertIn("pit_audit_not_passed", pit["blocking_reasons"])

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _seed_ready_inputs(tmp)
            _write_json(Path(tmp) / "outputs" / "diagnostics" / "managed_data_quality_scorecard.json", {"status": "fail", "gate_passed": False})
            quality = build_v12_input_contract_report()
        self.assertIn("data_quality_not_passed", quality["blocking_reasons"])

    def test_all_pass_sets_input_ready_but_does_not_build_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.feature_store_v12_input_contract_service.build_feature_store_v12"
        ) as build_v12:
            _seed_ready_inputs(tmp)
            report = build_v12_input_contract_report()
            diff = compare_production_cache_against_v12_requirements()
            feature_store_v12 = Path(tmp) / "outputs" / "feature_store" / "v12" / "feature_store.csv"
            customer_predictions = Path(tmp) / "outputs" / "customer_predictions"

        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["input_contract_ready"])
        self.assertTrue(diff["input_contract_ready"])
        self.assertEqual(report["missing_required_fields"], [])
        self.assertEqual(report["missing_timestamp_fields"], [])
        self.assertFalse(report["feature_store_v12_build_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertFalse(feature_store_v12.exists())
        self.assertFalse(customer_predictions.exists())
        build_v12.assert_not_called()


if __name__ == "__main__":
    unittest.main()
