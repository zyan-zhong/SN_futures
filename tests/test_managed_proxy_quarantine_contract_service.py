from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_proxy_quarantine_contract_service import (
    build_quarantine_contract_report,
    promote_quarantine_to_research_cache,
    validate_research_cache_promotion_gate,
)


VALID_ROW = {
    "source_timestamp": "2024-01-02T14:00:00",
    "asof_date": "2024-01-02",
    "ingest_timestamp": "2024-01-02T18:00:00",
    "feature_date": "2024-01-03",
    "prediction_cutoff_date": "2024-01-03",
    "spot_price": 205000,
    "spot_premium": 120,
    "spot_futures_basis": 80,
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


def _write_snapshot(tmp: str, rows: list[dict[str, object]], **report_overrides: object) -> Path:
    out = Path(tmp) / "outputs"
    diagnostics = out / "diagnostics"
    quarantine = out / "managed_proxy_quarantine"
    diagnostics.mkdir(parents=True, exist_ok=True)
    quarantine.mkdir(parents=True, exist_ok=True)
    snapshot_path = quarantine / "managed_proxy_quarantine_snapshot_test.json"
    snapshot_path.write_text(
        json.dumps(
            {
                "quarantine_only": True,
                "production_eligible": False,
                "feature_store_v12_allowed": False,
                "rows": rows,
            }
        ),
        encoding="utf-8",
    )
    report = {
        "status": "ready",
        "snapshot_pulled": True,
        "snapshot_row_count": len(rows),
        "row_count": len(rows),
        "secret_safety_status": "pass",
        "quarantine_path": str(snapshot_path),
        "production_eligible": False,
        "feature_store_v12_allowed": False,
        "sample_data_used": False,
        "customer_prediction_generated": False,
        "active_updated": False,
        "training_invoked": False,
        "blocking_reasons": [],
    }
    report.update(report_overrides)
    (diagnostics / "managed_proxy_quarantine_snapshot_report.json").write_text(json.dumps(report), encoding="utf-8")
    return snapshot_path


class ManagedProxyQuarantineContractServiceTest(unittest.TestCase):
    def test_missing_quarantine_snapshot_blocks_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            report = build_quarantine_contract_report()
            research_cache = Path(tmp) / "outputs" / "managed_proxy_research_cache"
            fundamentals = Path(tmp) / "outputs" / "fundamentals"

        self.assertEqual(report["status"], "blocked")
        self.assertIn("quarantine_snapshot_report_missing", report["blocking_reasons"])
        self.assertFalse(report["research_cache_promotion_allowed"])
        self.assertFalse(report["research_cache_written"])
        self.assertFalse(report["production_eligible"])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertFalse(research_cache.exists())
        self.assertFalse(fundamentals.exists())

    def test_valid_quarantine_snapshot_contract_is_ready_but_not_production_eligible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            source = _write_snapshot(tmp, [VALID_ROW])
            report = build_quarantine_contract_report()

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["source_quarantine_path"], str(source))
        self.assertEqual(report["row_count"], 1)
        self.assertEqual(report["schema_contract_status"], "ready")
        self.assertEqual(report["pit_replay_status"], "ready")
        self.assertEqual(report["pit_audit_status"], "ready")
        self.assertEqual(report["data_quality_status"], "pass")
        self.assertTrue(report["research_cache_promotion_allowed"])
        self.assertFalse(report["research_cache_written"])
        self.assertFalse(report["production_eligible"])
        self.assertFalse(report["feature_store_v12_allowed"])

    def test_contract_failures_block_research_cache_promotion(self) -> None:
        leaking_row = dict(VALID_ROW)
        leaking_row["source_timestamp"] = "2024-01-04T12:00:00"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_snapshot(tmp, [leaking_row])
            report = build_quarantine_contract_report()
            gate = validate_research_cache_promotion_gate(report)
            promoted = promote_quarantine_to_research_cache()
            research_cache = Path(tmp) / "outputs" / "managed_proxy_research_cache"

        self.assertEqual(report["status"], "blocked")
        self.assertIn("pit_replay_failed", report["blocking_reasons"])
        self.assertFalse(gate["research_cache_promotion_allowed"])
        self.assertFalse(promoted["research_cache_written"])
        self.assertFalse(research_cache.exists())

    def test_promote_quarantine_to_research_cache_only_after_all_contracts_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_snapshot(tmp, [VALID_ROW])
            promoted = promote_quarantine_to_research_cache()
            cache_path = Path(str(promoted["research_cache_path"]))
            cache_payload = json.loads(cache_path.read_text(encoding="utf-8"))
            forbidden_fundamentals = Path(tmp) / "outputs" / "fundamentals" / "managed_fundamentals.json"

        self.assertEqual(promoted["status"], "ready")
        self.assertTrue(promoted["research_cache_promotion_allowed"])
        self.assertTrue(promoted["research_cache_written"])
        self.assertIn("managed_proxy_research_cache", str(cache_path))
        self.assertFalse(forbidden_fundamentals.exists())
        self.assertTrue(cache_payload["research_cache"])
        self.assertFalse(cache_payload["production_eligible"])
        self.assertFalse(cache_payload["feature_store_v12_allowed"])
        self.assertEqual(cache_payload["row_count"], 1)
        self.assertFalse(promoted["training_invoked"])
        self.assertFalse(promoted["active_updated"])
        self.assertFalse(promoted["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
