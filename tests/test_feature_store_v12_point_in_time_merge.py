from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v12_service import build_feature_store_v12, merge_managed_fundamentals_point_in_time


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


def _managed_row(feature_date: str, asof_date: str, source_timestamp: str, **overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "feature_date": feature_date,
        "source_timestamp": source_timestamp,
        "asof_date": asof_date,
        "ingest_timestamp": "2026-01-10T10:00:00",
        "prediction_cutoff_date": feature_date,
        **REQUIRED_FIELDS,
    }
    row.update(overrides)
    return row


class FeatureStoreV12PointInTimeMergeTest(unittest.TestCase):
    def test_merge_selects_latest_available_row_before_cutoff(self) -> None:
        market = pd.DataFrame(
            [
                {"trade_date": "2026-01-03", "prediction_cutoff_date": "2026-01-03", "close": 210000.0},
            ]
        )
        rows = [
            _managed_row("2026-01-03", "2026-01-01", "2026-01-01T09:00:00", spot_price=209000.0),
            _managed_row("2026-01-03", "2026-01-02", "2026-01-02T09:00:00", spot_price=211000.0),
            _managed_row("2026-01-03", "2026-01-04", "2026-01-04T09:00:00", spot_price=999999.0),
        ]

        merged = merge_managed_fundamentals_point_in_time(market, rows)

        self.assertEqual(float(merged.loc[0, "spot_price"]), 211000.0)
        self.assertEqual(str(merged.loc[0, "managed_asof_date"]), "2026-01-02")
        self.assertEqual(str(merged.loc[0, "managed_source_timestamp"]), "2026-01-02T09:00:00")

    def test_merge_does_not_forward_fill_future_managed_rows(self) -> None:
        market = pd.DataFrame(
            [
                {"trade_date": "2026-01-03", "prediction_cutoff_date": "2026-01-03", "close": 210000.0},
            ]
        )
        rows = [
            _managed_row("2026-01-04", "2026-01-04", "2026-01-04T09:00:00", spot_price=999999.0),
        ]

        merged = merge_managed_fundamentals_point_in_time(market, rows)

        self.assertTrue(pd.isna(merged.loc[0, "spot_price"]))
        self.assertTrue(pd.isna(merged.loc[0, "managed_asof_date"]))

    def test_ready_fixture_builds_feature_store_v12_with_real_managed_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output_dir = Path(tmp) / "outputs"
            v10_dir = output_dir / "feature_store" / "v10"
            fundamentals_dir = output_dir / "fundamentals"
            diagnostics_dir = output_dir / "diagnostics"
            v10_dir.mkdir(parents=True)
            fundamentals_dir.mkdir(parents=True)
            diagnostics_dir.mkdir(parents=True)
            base_path = v10_dir / "feature_store.csv"
            pd.DataFrame(
                [
                    {"trade_date": "2026-01-03", "prediction_cutoff_date": "2026-01-03", "close": 210000.0, "ret_1d": 0.01},
                    {"trade_date": "2026-01-04", "prediction_cutoff_date": "2026-01-04", "close": 211000.0, "ret_1d": -0.01},
                ]
            ).to_csv(base_path, index=False)
            rows = [
                _managed_row("2026-01-03", "2026-01-02", "2026-01-02T09:00:00", spot_price=211000.0),
                _managed_row("2026-01-04", "2026-01-04", "2026-01-04T09:00:00", spot_price=212000.0),
            ]
            (fundamentals_dir / "managed_fundamentals.json").write_text(
                json.dumps({"status": "success", "rows": rows}, ensure_ascii=False),
                encoding="utf-8",
            )
            (diagnostics_dir / "managed_data_quality_scorecard.json").write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "gate_passed": True,
                        "quality_score": 1.0,
                        "blocking_reasons": [],
                        "warning_reasons": [],
                        "training_invoked": False,
                        "active_updated": False,
                        "customer_prediction_generated": False,
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (diagnostics_dir / "managed_data_production_cache_gate_report.json").write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "production_cache_write_allowed": True,
                        "production_cache_written": True,
                        "feature_store_v12_allowed": True,
                        "blocking_reasons": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (diagnostics_dir / "feature_store_v12_input_contract_report.json").write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "input_contract_ready": True,
                        "feature_store_v12_build_allowed": False,
                        "blocking_reasons": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch(
                "sn_futures.services.feature_store_v12_service.load_latest_managed_health",
                return_value={"status": "ready", "provider_status": "success_with_required_fields", "v12_allowed": True, "blocking_reasons": []},
            ), patch(
                "sn_futures.services.feature_store_v12_service.load_latest_managed_audit",
                return_value={
                    "status": "ready",
                    "v12_allowed": True,
                    "blocking_reasons": [],
                    "missing_timestamp_fields": [],
                    "missing_fundamental_fields": [],
                    "field_timestamp_coverage": {"complete_ratio": 1.0},
                    "leakage_checks": {
                        "source_timestamp_leakage_pass": True,
                        "asof_date_leakage_pass": True,
                        "feature_date_cutoff_pass": True,
                        "ingest_timestamp_not_used_as_asof_pass": True,
                        "point_in_time_join_ready": True,
                    },
                },
            ), patch(
                "sn_futures.services.feature_store_v12_service.build_feature_store_v10",
                return_value={"status": "success", "feature_store_path": str(base_path), "row_count": 2, "usable_fields": ["close"]},
            ):
                result = build_feature_store_v12()

            frame = pd.read_csv(result["feature_store_path"])
            store_exists = Path(result["feature_store_path"]).exists()

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["feature_store_version"], "v12")
        self.assertTrue(store_exists)
        self.assertTrue(result["managed_data_used"])
        self.assertFalse(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertIn("spot_futures_basis", frame.columns)
        self.assertEqual(float(frame.loc[0, "spot_price"]), 211000.0)
        self.assertEqual(float(frame.loc[1, "spot_price"]), 212000.0)


if __name__ == "__main__":
    unittest.main()
