from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_data_production_cache_gate_service import (
    build_production_cache_gate_report,
    build_production_cache_promotion_dry_run,
    validate_production_cache_promotion_preconditions,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _ready_row(feature_date: str) -> dict[str, object]:
    return {
        "feature_date": feature_date,
        "prediction_cutoff_date": feature_date,
        "source_timestamp": feature_date,
        "asof_date": feature_date,
        "ingest_timestamp": f"{feature_date}T18:00:00",
        "spot_price": 221000,
        "spot_premium": 200,
        "spot_futures_basis": 250,
        "shfe_inventory": 1000,
        "shfe_warehouse_receipt": 900,
        "lme_tin_close": 30500,
        "lme_inventory": 4200,
        "near_contract_close": 221200,
        "near_open_interest": 10000,
        "far_contract_close": 222000,
        "far_open_interest": 8000,
        "main_contract_switch_flag": 0,
    }


def _seed_ready_inputs(tmp: str) -> Path:
    out = Path(tmp) / "outputs"
    diagnostics = out / "diagnostics"
    model_research = out / "model_research"
    cache_path = out / "managed_proxy_research_cache" / "managed_proxy_research_cache_ready.json"
    rows = [_ready_row("2024-01-03"), _ready_row("2024-01-04")]
    _write_json(
        cache_path,
        {
            "research_cache": True,
            "production_eligible": False,
            "feature_store_v12_allowed": False,
            "sample_data_used": False,
            "fixture_only": False,
            "row_count": len(rows),
            "date_range": {"date_start": "2024-01-03", "date_end": "2024-01-04"},
            "rows": rows,
        },
    )
    _write_json(
        diagnostics / "managed_proxy_endpoint_smoke_report.json",
        {
            "status": "pass",
            "auth_status": "pass",
            "endpoint_reachable": True,
            "response_format_status": "pass",
            "token_echo_status": "pass",
            "sample_row_count": 2,
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_proxy_quarantine_snapshot_report.json",
        {
            "status": "ready",
            "snapshot_pulled": True,
            "snapshot_row_count": 2,
            "production_eligible": False,
            "feature_store_v12_allowed": False,
        },
    )
    _write_json(
        diagnostics / "managed_proxy_quarantine_contract_report.json",
        {
            "status": "ready",
            "research_cache_promotion_allowed": True,
            "research_cache_written": True,
            "research_cache_path": str(cache_path),
            "schema_contract_status": "ready",
            "pit_replay_status": "ready",
            "pit_audit_status": "ready",
            "data_quality_status": "pass",
            "production_eligible": False,
            "feature_store_v12_allowed": False,
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_data_backfill_planner_report.json",
        {
            "status": "ready",
            "required_date_range": {"date_start": "2021-01-04", "date_end": "2024-12-31"},
            "target_horizons": ["1d", "5d", "10d", "20d"],
            "coverage_budget": {
                "min_row_count": 720,
                "min_date_coverage_ratio": 0.95,
                "max_missing_rate_by_required_field": {"spot_price": 0.05},
                "min_timestamp_coverage": 1.0,
                "min_pit_replay_pass_rate": 1.0,
                "min_quality_score": 0.9,
                "allowed_duplicate_key_count": 0,
            },
            "batch_plan": {"status": "ready", "batch_count": 12, "dry_run_only": True},
            "production_cache_write_allowed": False,
            "feature_store_v12_allowed": False,
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_pit_replay_report.json",
        {
            "status": "ready",
            "point_in_time_join_ready": True,
            "cases_passed": 2,
            "cases_failed": 0,
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_data_audit_manifest.json",
        {
            "status": "ready",
            "v12_allowed": True,
            "ready": True,
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
        {
            "status": "pass",
            "gate_passed": True,
            "quality_score": 0.98,
            "blocking_reasons": [],
        },
    )
    _write_json(
        model_research / "evidence_freshness_report.json",
        {
            "status": "pass",
            "stale_reports": [],
            "missing_timestamps": [],
            "timestamp_inversions": [],
            "blocking_reasons": [],
        },
    )
    _write_json(
        model_research / "incident_drill_report.json",
        {
            "status": "pass",
            "real_lockdown_state": {"lockdown_triggered": False, "lockdown_reasons": []},
            "blocking_reasons": [],
        },
    )
    _write_json(
        model_research / "manual_approval_report.json",
        {
            "status": "approved",
            "approval_decision": "approved",
            "requested_action": "production_managed_cache_promotion",
            "two_person_review_pass": True,
            "expires_at": "2999-01-01T00:00:00",
            "blocking_reasons": [],
        },
    )
    _write_json(diagnostics / "runtime_secret_scan.json", {"status": "pass", "finding_count": 0, "complete_key_leakage_detected": False})
    return cache_path


class ManagedDataProductionCacheGateServiceTest(unittest.TestCase):
    def test_missing_research_cache_blocks_and_does_not_write_production_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            report = build_production_cache_gate_report()
            fundamentals = Path(tmp) / "outputs" / "fundamentals" / "managed_fundamentals.json"
            feature_store_v12 = Path(tmp) / "outputs" / "feature_store" / "v12" / "feature_store.csv"

        self.assertEqual(report["status"], "blocked")
        self.assertIn("research_cache_missing", report["blocking_reasons"])
        self.assertFalse(report["production_cache_write_allowed"])
        self.assertFalse(report["production_cache_written"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertFalse(fundamentals.exists())
        self.assertFalse(feature_store_v12.exists())

    def test_blocked_upstream_reports_keep_gate_blocked(self) -> None:
        cases = [
            ("managed_data_backfill_planner_report.json", {"status": "blocked", "coverage_budget": {}}, "backfill_planner_blocked"),
            ("managed_pit_replay_report.json", {"status": "blocked", "point_in_time_join_ready": False}, "pit_replay_not_passed"),
            ("managed_data_audit_manifest.json", {"status": "blocked", "v12_allowed": False}, "pit_audit_not_passed"),
            ("managed_data_quality_scorecard.json", {"status": "fail", "gate_passed": False}, "managed_data_quality_not_passed"),
        ]
        for filename, payload, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
                _seed_ready_inputs(tmp)
                _write_json(Path(tmp) / "outputs" / "diagnostics" / filename, payload)
                report = validate_production_cache_promotion_preconditions()

            self.assertEqual(report["status"], "blocked")
            self.assertIn(reason, report["blocking_reasons"])

    def test_missing_manual_approval_or_lockdown_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _seed_ready_inputs(tmp)
            (Path(tmp) / "outputs" / "model_research" / "manual_approval_report.json").unlink()
            missing_approval = validate_production_cache_promotion_preconditions()
        self.assertIn("manual_approval_missing_or_not_approved", missing_approval["blocking_reasons"])

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _seed_ready_inputs(tmp)
            _write_json(
                Path(tmp) / "outputs" / "model_research" / "incident_drill_report.json",
                {"status": "pass", "real_lockdown_state": {"lockdown_triggered": True, "lockdown_reasons": ["simulated_violation"]}},
            )
            lockdown = validate_production_cache_promotion_preconditions()
        self.assertIn("governance_lockdown_active", lockdown["blocking_reasons"])

    def test_all_preconditions_ready_only_generates_dry_run_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            cache_path = _seed_ready_inputs(tmp)
            report = build_production_cache_gate_report()
            dry_run = build_production_cache_promotion_dry_run()
            fundamentals = Path(tmp) / "outputs" / "fundamentals" / "managed_fundamentals.json"
            feature_store_v12 = Path(tmp) / "outputs" / "feature_store" / "v12" / "feature_store.csv"
            active_model = Path(tmp) / "outputs" / "model_registry" / "active_model.json"
            customer_predictions = Path(tmp) / "outputs" / "customer_predictions"

        self.assertEqual(report["status"], "ready")
        self.assertEqual(dry_run["status"], "ready")
        self.assertEqual(dry_run["source_research_cache_path"], str(cache_path))
        self.assertEqual(dry_run["expected_row_count"], 2)
        self.assertIn("no write performed", dry_run["explicit_note"].lower())
        self.assertFalse(report["production_cache_write_allowed"])
        self.assertFalse(report["production_cache_written"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertIn("research cache is not production cache", " ".join(report["warning_reasons"]).lower())
        self.assertFalse(fundamentals.exists())
        self.assertFalse(feature_store_v12.exists())
        self.assertFalse(active_model.exists())
        self.assertFalse(customer_predictions.exists())


if __name__ == "__main__":
    unittest.main()
