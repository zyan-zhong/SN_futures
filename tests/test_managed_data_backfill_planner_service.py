from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_data_backfill_planner_service import (
    build_real_managed_data_backfill_plan,
    write_backfill_planner_report,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_ready_inputs(tmp: str) -> None:
    out = Path(tmp) / "outputs"
    diagnostics = out / "diagnostics"
    cache = out / "managed_proxy_research_cache"
    cache.mkdir(parents=True, exist_ok=True)
    cache_path = cache / "managed_proxy_research_cache_test.json"
    _write_json(
        cache_path,
        {
            "research_cache": True,
            "production_eligible": False,
            "feature_store_v12_allowed": False,
            "row_count": 2,
            "rows": [{"feature_date": "2024-01-03"}, {"feature_date": "2024-01-04"}],
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
            "sample_row_count": 1,
            "blocking_reasons": [],
        },
    )
    _write_json(
        diagnostics / "managed_proxy_quarantine_snapshot_report.json",
        {
            "status": "ready",
            "snapshot_pulled": True,
            "snapshot_row_count": 2,
            "secret_safety_status": "pass",
            "production_eligible": False,
            "feature_store_v12_allowed": False,
        },
    )
    _write_json(
        diagnostics / "managed_proxy_quarantine_contract_report.json",
        {
            "status": "ready",
            "row_count": 2,
            "schema_contract_status": "ready",
            "pit_replay_status": "ready",
            "pit_audit_status": "ready",
            "data_quality_status": "pass",
            "research_cache_promotion_allowed": True,
            "research_cache_written": True,
            "research_cache_path": str(cache_path),
            "production_eligible": False,
            "feature_store_v12_allowed": False,
            "blocking_reasons": [],
        },
    )
    _write_json(
        out / "feature_store" / "v10" / "feature_store_manifest.json",
        {"status": "success", "date_start": "2021-01-04", "date_end": "2024-12-31", "row_count": 720},
    )


class ManagedDataBackfillPlannerServiceTest(unittest.TestCase):
    def test_endpoint_smoke_blocked_keeps_plan_blocked_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            report = write_backfill_planner_report()
            fundamentals = Path(tmp) / "outputs" / "fundamentals" / "managed_fundamentals.json"
            feature_store_v12 = Path(tmp) / "outputs" / "feature_store" / "v12" / "feature_store.csv"

        self.assertEqual(report["status"], "blocked")
        self.assertIn("endpoint_smoke_not_passed", report["blocking_reasons"])
        self.assertFalse(report["production_cache_write_allowed"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertFalse(report["rows_fetched"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertFalse(fundamentals.exists())
        self.assertFalse(feature_store_v12.exists())

    def test_valid_preconditions_generate_ready_plan_without_fetching_or_building(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_ready_inputs(tmp)
            report = build_real_managed_data_backfill_plan()
            fundamentals = Path(tmp) / "outputs" / "fundamentals" / "managed_fundamentals.json"
            feature_store_v12 = Path(tmp) / "outputs" / "feature_store" / "v12" / "feature_store.csv"

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["required_date_range"]["date_start"], "2021-01-04")
        self.assertEqual(report["required_date_range"]["date_end"], "2024-12-31")
        self.assertGreaterEqual(report["coverage_budget"]["min_row_count"], 720)
        self.assertEqual(report["coverage_budget"]["allowed_duplicate_key_count"], 0)
        self.assertGreaterEqual(len(report["batch_plan"]["batches"]), 1)
        self.assertIn("token echo detected", report["abort_conditions"])
        self.assertFalse(report["production_cache_write_allowed"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertFalse(report["rows_fetched"])
        self.assertFalse(report["historical_backfill_executed"])
        self.assertFalse(fundamentals.exists())
        self.assertFalse(feature_store_v12.exists())

    def test_missing_date_range_blocks_or_warns_but_never_executes_backfill(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_ready_inputs(tmp)
            (Path(tmp) / "outputs" / "feature_store" / "v10" / "feature_store_manifest.json").unlink()
            report = build_real_managed_data_backfill_plan()

        self.assertIn(report["status"], {"blocked", "ready"})
        self.assertIn("v12_target_date_range_missing", report["blocking_reasons"] + report["warning_reasons"])
        self.assertFalse(report["rows_fetched"])
        self.assertFalse(report["production_cache_write_allowed"])


if __name__ == "__main__":
    unittest.main()
