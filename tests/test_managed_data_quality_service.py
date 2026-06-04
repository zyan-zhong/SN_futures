from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS
from sn_futures.services.managed_data_quality_service import (
    build_managed_data_quality_scorecard,
    compute_quality_gate,
    detect_basis_outliers,
    detect_contract_switch_anomalies,
    detect_duplicate_keys,
    detect_inventory_outliers,
    detect_negative_or_invalid_values,
    validate_required_field_null_rate,
)


def _row(day: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "feature_date": day,
        "trading_date": day,
        "asof_date": day,
        "source_timestamp": f"{day}T15:30:00",
        "ingest_timestamp": f"{day}T16:00:00",
        "prediction_cutoff_date": day,
        "spot_price": 100.0,
        "spot_premium": 1.0,
        "spot_futures_basis": 2.0,
        "shfe_inventory": 1000.0,
        "shfe_warehouse_receipt": 900.0,
        "lme_tin_close": 101.0,
        "lme_inventory": 500.0,
        "near_contract_close": 99.0,
        "near_open_interest": 10000.0,
        "far_contract_close": 98.0,
        "far_open_interest": 8000.0,
        "main_contract_switch_flag": 0,
    }
    row.update(overrides)
    return row


class ManagedDataQualityServiceTest(unittest.TestCase):
    def _env(self, tmp: str) -> patch:
        return patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_INSIGHT_DATA_DIR": ""}, clear=False)

    def test_required_field_null_rate_over_threshold_fails(self) -> None:
        rows = [_row("2026-05-01"), _row("2026-05-02", spot_price=None), _row("2026-05-03", spot_price=None)]

        result = validate_required_field_null_rate(rows, required_fields=["spot_price"], max_null_rate=0.2)

        self.assertEqual(result["status"], "fail")
        self.assertGreater(result["null_rate_by_field"]["spot_price"], 0.2)
        self.assertIn("null_rate_too_high:spot_price", result["blocking_reasons"])

    def test_timestamp_duplicate_key_fails(self) -> None:
        rows = [_row("2026-05-01"), _row("2026-05-01")]

        result = detect_duplicate_keys(rows)

        self.assertEqual(result["status"], "fail")
        self.assertEqual(result["duplicate_key_count"], 1)

    def test_negative_inventory_and_impossible_open_interest_fail(self) -> None:
        rows = [
            _row("2026-05-01", shfe_inventory=-1.0),
            _row("2026-05-02", near_open_interest=-100.0),
        ]

        result = detect_negative_or_invalid_values(rows)

        self.assertEqual(result["status"], "fail")
        self.assertGreaterEqual(result["invalid_value_count"], 2)
        self.assertIn("negative_inventory", result["blocking_reasons"])
        self.assertIn("impossible_open_interest", result["blocking_reasons"])

    def test_basis_extreme_jump_warns_or_fails(self) -> None:
        rows = [
            _row("2026-05-01", spot_futures_basis=1.0),
            _row("2026-05-02", spot_futures_basis=500.0),
        ]

        result = detect_basis_outliers(rows, max_absolute_basis=300.0, max_jump_abs=100.0)

        self.assertIn(result["status"], {"warning", "fail"})
        self.assertGreater(result["outlier_count"], 0)

    def test_inventory_outlier_detects_large_jump(self) -> None:
        rows = [
            _row("2026-05-01", shfe_inventory=1000.0),
            _row("2026-05-02", shfe_inventory=100000.0),
        ]

        result = detect_inventory_outliers(rows, max_inventory_jump_ratio=10.0)

        self.assertIn(result["status"], {"warning", "fail"})
        self.assertGreater(result["outlier_count"], 0)

    def test_contract_switch_anomaly_detects_consecutive_jumps(self) -> None:
        rows = [
            _row("2026-05-01", main_contract_switch_flag=1),
            _row("2026-05-02", main_contract_switch_flag=1),
            _row("2026-05-03", main_contract_switch_flag=1),
        ]

        result = detect_contract_switch_anomalies(rows, max_consecutive_switches=1)

        self.assertIn(result["status"], {"warning", "fail"})
        self.assertEqual(result["max_consecutive_switches"], 3)

    def test_success_fixture_passes_quality_gate(self) -> None:
        rows = [_row("2026-05-01"), _row("2026-05-02", spot_futures_basis=2.5)]

        scorecard = build_managed_data_quality_scorecard(rows=rows, write=False)

        self.assertEqual(scorecard["status"], "pass")
        self.assertTrue(scorecard["gate_passed"])
        self.assertGreaterEqual(scorecard["quality_score"], 0.9)
        self.assertEqual(scorecard["blocking_reasons"], [])
        self.assertFalse(scorecard["training_invoked"])
        self.assertFalse(scorecard["active_updated"])
        self.assertFalse(scorecard["customer_prediction_generated"])

    def test_empty_rows_are_blocked_and_manifest_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            scorecard = build_managed_data_quality_scorecard(rows=[])
            path = Path(scorecard["scorecard_path"])
            text = path.read_text(encoding="utf-8")

        self.assertEqual(scorecard["status"], "blocked")
        self.assertFalse(scorecard["gate_passed"])
        self.assertEqual(scorecard["quality_score"], 0.0)
        self.assertIn("managed_rows_missing", scorecard["blocking_reasons"])
        self.assertIn("training_invoked", text)

    def test_compute_quality_gate_combines_failures_and_warnings(self) -> None:
        gate = compute_quality_gate(
            row_count=3,
            null_rate_result={"blocking_reasons": ["null_rate_too_high:spot_price"]},
            duplicate_result={"duplicate_key_count": 0, "blocking_reasons": []},
            invalid_result={"invalid_value_count": 0, "blocking_reasons": []},
            outlier_summary={"blocking_reasons": [], "warning_reasons": ["basis_jump_outlier"]},
            contract_switch_summary={"blocking_reasons": [], "warning_reasons": []},
        )

        self.assertEqual(gate["status"], "fail")
        self.assertFalse(gate["gate_passed"])
        self.assertIn("null_rate_too_high:spot_price", gate["blocking_reasons"])
        self.assertIn("basis_jump_outlier", gate["warning_reasons"])

    def test_scorecard_does_not_leak_secret_like_values(self) -> None:
        rows = [_row("2026-05-01", note="Authorization: Bearer managed-secret-token")]

        scorecard = build_managed_data_quality_scorecard(rows=rows, write=False)
        serialized = json.dumps(scorecard, ensure_ascii=False)

        self.assertNotIn("managed-secret-token", serialized)
        self.assertNotIn("Authorization: Bearer", serialized)


if __name__ == "__main__":
    unittest.main()
