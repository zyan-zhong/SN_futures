from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v12_build_plan_service import (
    build_feature_store_v12_dry_run_plan,
    write_v12_build_plan_report,
)


REQUIRED_FIELDS = [
    "spot_price",
    "spot_premium",
    "spot_futures_basis",
    "shfe_inventory",
    "shfe_warehouse_receipt",
    "lme_tin_close",
    "lme_inventory",
    "near_contract_close",
    "near_open_interest",
    "far_contract_close",
    "far_open_interest",
    "main_contract_switch_flag",
]


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _seed_ready_inputs(tmp: str) -> None:
    out = Path(tmp) / "outputs"
    diagnostics = out / "diagnostics"
    model_research = out / "model_research"
    _write_json(
        diagnostics / "feature_store_v12_input_contract_report.json",
        {
            "status": "ready",
            "generated_at": "2026-06-04T09:00:00",
            "input_contract_ready": True,
            "feature_store_v12_build_allowed": False,
            "required_fields": REQUIRED_FIELDS,
            "missing_required_fields": [],
            "missing_timestamp_fields": [],
            "production_cache_path": str(out / "fundamentals" / "managed_fundamentals.json"),
            "coverage_diff": {"row_count": 128, "date_coverage_ratio": 0.98, "timestamp_complete_ratio": 1.0},
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_data_production_cache_gate_report.json",
        {
            "status": "ready",
            "generated_at": "2026-06-04T09:00:00",
            "production_cache_written": True,
            "production_cache_write_allowed": True,
            "feature_store_v12_allowed": True,
            "blocking_reasons": [],
        },
    )
    _write_json(
        model_research / "evidence_freshness_report.json",
        {
            "status": "ready",
            "generated_at": "2026-06-04T09:00:00",
            "stale_reports": [],
            "missing_timestamps": [],
            "timestamp_inversions": [],
            "blocking_reasons": [],
        },
    )


class FeatureStoreV12BuildPlanServiceTest(unittest.TestCase):
    def test_input_contract_blocked_blocks_plan_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _seed_ready_inputs(tmp)
            _write_json(
                Path(tmp) / "outputs" / "diagnostics" / "feature_store_v12_input_contract_report.json",
                {"status": "blocked", "input_contract_ready": False, "blocking_reasons": ["production_cache_missing"]},
            )
            report = write_v12_build_plan_report()
            feature_store = Path(tmp) / "outputs" / "feature_store" / "v12" / "feature_store.csv"
            training_dataset = Path(tmp) / "outputs" / "training_datasets" / "v12"

        self.assertEqual(report["status"], "blocked")
        self.assertIn("input_contract_blocked", report["blocking_reasons"])
        self.assertFalse(report["feature_store_v12_build_executed"])
        self.assertFalse(feature_store.exists())
        self.assertFalse(training_dataset.exists())

    def test_evidence_stale_and_production_cache_not_written_block_plan(self) -> None:
        cases = [
            (
                "evidence_stale",
                "model_research/evidence_freshness_report.json",
                {"status": "blocked", "stale_reports": ["managed_data_quality"], "blocking_reasons": ["freshness:managed_data_quality_stale"]},
                "evidence_freshness_blocked",
            ),
            (
                "cache_not_written",
                "diagnostics/managed_data_production_cache_gate_report.json",
                {"status": "ready", "production_cache_written": False, "feature_store_v12_allowed": False, "blocking_reasons": []},
                "production_cache_not_written",
            ),
        ]
        for _, rel_path, payload, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
                _seed_ready_inputs(tmp)
                _write_json(Path(tmp) / "outputs" / rel_path, payload)
                report = build_feature_store_v12_dry_run_plan()
            self.assertEqual(report["status"], "blocked")
            self.assertIn(reason, report["blocking_reasons"])
            self.assertFalse(report["feature_store_v12_build_executed"])

    def test_all_preconditions_ready_produces_ready_plan_but_builds_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _seed_ready_inputs(tmp)
            report = write_v12_build_plan_report()
            feature_store = Path(tmp) / "outputs" / "feature_store" / "v12" / "feature_store.csv"
            manifest = Path(tmp) / "outputs" / "feature_store" / "v12" / "feature_store_manifest.json"
            active_model = Path(tmp) / "outputs" / "model_registry" / "active_model.json"
            customer_predictions = Path(tmp) / "outputs" / "customer_predictions"

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["input_contract_status"], "ready")
        self.assertEqual(report["expected_row_count"], 128)
        self.assertIn("rollback_delete_new_feature_store_v12_outputs", report["rollback_plan"])
        self.assertIn("build_feature_store_v12", report["forbidden_side_effects"])
        self.assertFalse(report["feature_store_v12_build_executed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertFalse(feature_store.exists())
        self.assertFalse(manifest.exists())
        self.assertFalse(active_model.exists())
        self.assertFalse(customer_predictions.exists())


if __name__ == "__main__":
    unittest.main()
