from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v12_controlled_build_service import (
    execute_feature_store_v12_controlled_build,
    validate_v12_controlled_build_preconditions,
)


REQUIRED_FIELDS = {
    "spot_price": 212000,
    "spot_premium": 120,
    "spot_futures_basis": 80,
    "shfe_inventory": 3800,
    "shfe_warehouse_receipt": 2100,
    "lme_tin_close": 28800,
    "lme_inventory": 4500,
    "near_contract_close": 212100,
    "near_open_interest": 120000,
    "far_contract_close": 213000,
    "far_open_interest": 90000,
    "main_contract_switch_flag": 0,
}


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _seed_ready_inputs(tmp: str) -> Path:
    out = Path(tmp) / "outputs"
    diagnostics = out / "diagnostics"
    model_research = out / "model_research"
    rows = [
        {
            "feature_date": "2026-01-02",
            "trading_date": "2026-01-02",
            "prediction_cutoff_date": "2026-01-02",
            "source_timestamp": "2026-01-02T08:45:00",
            "asof_date": "2026-01-02",
            "ingest_timestamp": "2026-01-02T09:05:00",
            **REQUIRED_FIELDS,
        },
        {
            "feature_date": "2026-01-03",
            "trading_date": "2026-01-03",
            "prediction_cutoff_date": "2026-01-03",
            "source_timestamp": "2026-01-03T08:45:00",
            "asof_date": "2026-01-03",
            "ingest_timestamp": "2026-01-03T09:05:00",
            **{**REQUIRED_FIELDS, "spot_price": 213000, "main_contract_switch_flag": 1},
        },
    ]
    _write_json(out / "fundamentals" / "managed_fundamentals.json", {"rows": rows})
    _write_json(
        diagnostics / "managed_data_production_cache_gate_report.json",
        {
            "status": "ready",
            "production_cache_written": True,
            "production_cache_write_allowed": True,
            "feature_store_v12_allowed": True,
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "feature_store_v12_input_contract_report.json",
        {
            "status": "ready",
            "input_contract_ready": True,
            "feature_store_v12_build_allowed": False,
            "required_fields": list(REQUIRED_FIELDS.keys()),
            "missing_required_fields": [],
            "missing_timestamp_fields": [],
            "coverage_diff": {"row_count": len(rows), "date_coverage_ratio": 1.0, "timestamp_complete_ratio": 1.0},
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "feature_store_v12_build_plan_report.json",
        {
            "status": "ready",
            "feature_store_v12_build_executed": False,
            "expected_feature_store_path": str(out / "feature_store" / "v12" / "feature_store.csv"),
            "expected_manifest_path": str(out / "feature_store" / "v12" / "feature_store_manifest.json"),
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_pit_replay_report.json",
        {
            "status": "ready",
            "point_in_time_join_ready": True,
            "cases_failed": 0,
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_data_audit_manifest.json",
        {
            "status": "ready",
            "point_in_time_join_ready": True,
            "leakage_checks": {
                "source_timestamp_leakage_pass": True,
                "asof_date_leakage_pass": True,
                "feature_date_cutoff_pass": True,
                "point_in_time_join_ready": True,
            },
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_data_quality_scorecard.json",
        {"status": "pass", "gate_passed": True, "quality_score": 0.98, "blocking_reasons": []},
    )
    _write_json(
        model_research / "evidence_freshness_report.json",
        {"status": "ready", "stale_reports": [], "missing_timestamps": [], "timestamp_inversions": [], "blocking_reasons": []},
    )
    _write_json(
        model_research / "incident_drill_report.json",
        {"status": "completed", "real_lockdown_state": False, "lockdown_triggered": True, "simulated_artifacts_only": True},
    )
    return out


class FeatureStoreV12ControlledBuildServiceTest(unittest.TestCase):
    def test_blocked_inputs_write_report_only_and_no_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = _seed_ready_inputs(tmp)
            _write_json(
                out / "diagnostics" / "managed_data_production_cache_gate_report.json",
                {"status": "blocked", "production_cache_written": False, "blocking_reasons": ["production_cache_not_written"]},
            )

            report = execute_feature_store_v12_controlled_build()

            feature_store = out / "feature_store" / "v12" / "feature_store.csv"
            controlled_manifest = out / "feature_store" / "v12" / "feature_store_controlled_build_manifest.json"
            training_dataset = out / "training_datasets" / "v12"
            candidate = out / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json"

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["build_executed"])
        self.assertIn("production_cache_gate_blocked", report["blocking_reasons"])
        self.assertFalse(feature_store.exists())
        self.assertFalse(controlled_manifest.exists())
        self.assertFalse(training_dataset.exists())
        self.assertFalse(candidate.exists())
        self.assertFalse(report["training_dataset_v12_triggered"])
        self.assertFalse(report["candidate_triggered"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_unexpected_active_or_customer_predictions_block_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = _seed_ready_inputs(tmp)
            _write_json(out / "model_registry" / "active_model.json", {"model": "unexpected"})
            (out / "customer_predictions").mkdir(parents=True)

            preconditions = validate_v12_controlled_build_preconditions()

        self.assertEqual(preconditions["status"], "blocked")
        self.assertIn("unexpected_active_model_json_exists", preconditions["blocking_reasons"])
        self.assertIn("unexpected_customer_predictions_exists", preconditions["blocking_reasons"])

    def test_ready_fixture_executes_only_controlled_v12_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = _seed_ready_inputs(tmp)

            report = execute_feature_store_v12_controlled_build()

            feature_store = out / "feature_store" / "v12" / "feature_store.csv"
            controlled_manifest = out / "feature_store" / "v12" / "feature_store_controlled_build_manifest.json"
            standard_manifest = out / "feature_store" / "v12" / "feature_store_manifest.json"
            training_dataset = out / "training_datasets" / "v12"
            candidate = out / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json"
            active_model = out / "model_registry" / "active_model.json"
            customer_predictions = out / "customer_predictions"
            exists = {
                "feature_store": feature_store.exists(),
                "controlled_manifest": controlled_manifest.exists(),
                "standard_manifest": standard_manifest.exists(),
                "training_dataset": training_dataset.exists(),
                "candidate": candidate.exists(),
                "active_model": active_model.exists(),
                "customer_predictions": customer_predictions.exists(),
            }

        self.assertEqual(report["status"], "success")
        self.assertTrue(report["build_executed"])
        self.assertEqual(report["row_count"], 2)
        self.assertTrue(exists["feature_store"])
        self.assertTrue(exists["controlled_manifest"])
        self.assertFalse(exists["standard_manifest"])
        self.assertFalse(exists["training_dataset"])
        self.assertFalse(exists["candidate"])
        self.assertFalse(exists["active_model"])
        self.assertFalse(exists["customer_predictions"])
        self.assertFalse(report["training_dataset_v12_triggered"])
        self.assertFalse(report["candidate_triggered"])
        self.assertFalse(report["training_invoked"])
        self.assertIn("no_raw_token_in_artifacts", report["artifact_boundary_checks"])
        self.assertIs(report["artifact_boundary_checks"]["no_raw_token_in_artifacts"], True)

    def test_report_sanitizes_secret_like_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = _seed_ready_inputs(tmp)
            _write_json(
                out / "diagnostics" / "feature_store_v12_input_contract_report.json",
                {
                    "status": "blocked",
                    "input_contract_ready": False,
                    "blocking_reasons": ["Authorization Bearer sk-secret-token"],
                },
            )

            report = execute_feature_store_v12_controlled_build()
            rendered = json.dumps(report, ensure_ascii=False)

        self.assertNotIn("sk-secret-token", rendered)
        self.assertIn("***", rendered)


if __name__ == "__main__":
    unittest.main()
