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

from sn_futures.services.feature_store_v12_service import build_feature_store_v12


REQUIRED_MANAGED_FIELDS = {
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


class ManagedDataAuditV12GateTest(unittest.TestCase):
    def test_v12_blocked_when_health_ready_but_audit_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.feature_store_v12_service.get_managed_proxy_health",
            return_value={"status": "ready", "v12_allowed": True, "blocking_reasons": []},
        ), patch(
            "sn_futures.services.feature_store_v12_service.compute_managed_audit_readiness",
            return_value={"status": "blocked", "ready": False, "v12_allowed": False, "blocking_reasons": ["missing_asof_date"]},
        ):
            result = build_feature_store_v12()

        self.assertEqual(result["status"], "blocked")
        self.assertIn("missing_asof_date", result["managed_audit_readiness"]["blocking_reasons"])
        self.assertFalse(result["active_model_written"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_v12_blocked_when_audit_leakage_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.feature_store_v12_service.get_managed_proxy_health",
            return_value={"status": "ready", "v12_allowed": True, "blocking_reasons": []},
        ), patch(
            "sn_futures.services.feature_store_v12_service.compute_managed_audit_readiness",
            return_value={
                "status": "blocked",
                "ready": False,
                "v12_allowed": False,
                "blocking_reasons": ["source_timestamp_leakage"],
                "leakage_checks": {"source_timestamp_leakage_pass": False},
            },
        ):
            result = build_feature_store_v12()

        self.assertEqual(result["status"], "blocked")
        self.assertIn("source_timestamp_leakage", result["managed_audit_readiness"]["blocking_reasons"])

    def test_v12_allowed_only_when_health_audit_and_quality_pass(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output_dir = Path(tmp) / "outputs"
            v10_dir = output_dir / "feature_store" / "v10"
            fundamentals_dir = output_dir / "fundamentals"
            diagnostics_dir = output_dir / "diagnostics"
            v10_dir.mkdir(parents=True)
            fundamentals_dir.mkdir(parents=True)
            diagnostics_dir.mkdir(parents=True)
            base_path = v10_dir / "feature_store.csv"
            pd.DataFrame([{"trade_date": "2026-01-03", "prediction_cutoff_date": "2026-01-03", "close": 210000.0}]).to_csv(base_path, index=False)
            (fundamentals_dir / "managed_fundamentals.json").write_text(
                json.dumps(
                    {
                        "rows": [
                            {
                                "feature_date": "2026-01-03",
                                "source_timestamp": "2026-01-02T09:00:00",
                                "asof_date": "2026-01-02",
                                "ingest_timestamp": "2026-01-04T10:00:00",
                                "prediction_cutoff_date": "2026-01-03",
                                **REQUIRED_MANAGED_FIELDS,
                            }
                        ]
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (diagnostics_dir / "managed_data_quality_scorecard.json").write_text(
                json.dumps({"status": "pass", "gate_passed": True, "blocking_reasons": [], "warning_reasons": []}, ensure_ascii=False),
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
                        "blocking_reasons": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            with patch(
                "sn_futures.services.feature_store_v12_service.get_managed_proxy_health",
                return_value={"status": "ready", "provider_status": "success_with_required_fields", "v12_allowed": True, "blocking_reasons": []},
            ), patch(
                "sn_futures.services.feature_store_v12_service.compute_managed_audit_readiness",
                return_value={"status": "ready", "ready": True, "v12_allowed": True, "blocking_reasons": []},
            ), patch(
                "sn_futures.services.feature_store_v12_service.build_feature_store_v10",
                return_value={"status": "success", "feature_store_path": str(base_path), "row_count": 1},
            ):
                result = build_feature_store_v12()

        self.assertEqual(result["status"], "success")
        self.assertTrue(result["managed_proxy_readiness"]["v12_allowed"])
        self.assertTrue(result["managed_audit_readiness"]["v12_allowed"])


if __name__ == "__main__":
    unittest.main()
