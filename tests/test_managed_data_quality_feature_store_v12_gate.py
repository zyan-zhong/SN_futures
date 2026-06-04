from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v12_service import validate_v12_managed_readiness


class ManagedDataQualityFeatureStoreV12GateTest(unittest.TestCase):
    def test_quality_missing_blocks_feature_store_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            readiness = validate_v12_managed_readiness(
                health={"status": "ready", "provider_status": "success_with_required_fields", "v12_allowed": True, "blocking_reasons": []},
                audit={"status": "ready", "v12_allowed": True, "blocking_reasons": [], "leakage_checks": {"point_in_time_join_ready": True}},
                schema_mapping={"status": "ready", "schema_mapping_ready": True, "blocking_reasons": []},
                managed_rows=[{"feature_date": "2026-05-01"}],
            )

        self.assertFalse(readiness["v12_allowed"])
        self.assertIn("managed_data_quality_missing", readiness["blocking_reasons"])

    def test_quality_fail_blocks_feature_store_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            diagnostics.mkdir(parents=True, exist_ok=True)
            (diagnostics / "managed_data_quality_scorecard.json").write_text(
                json.dumps({"status": "fail", "gate_passed": False, "blocking_reasons": ["negative_inventory"], "warning_reasons": []}),
                encoding="utf-8",
            )
            readiness = validate_v12_managed_readiness(
                health={"status": "ready", "provider_status": "success_with_required_fields", "v12_allowed": True, "blocking_reasons": []},
                audit={"status": "ready", "v12_allowed": True, "blocking_reasons": [], "leakage_checks": {"point_in_time_join_ready": True}},
                schema_mapping={"status": "ready", "schema_mapping_ready": True, "blocking_reasons": []},
                managed_rows=[{"feature_date": "2026-05-01"}],
            )

        self.assertFalse(readiness["v12_allowed"])
        self.assertIn("managed_data_quality:negative_inventory", readiness["blocking_reasons"])

    def test_quality_warning_is_carried_but_not_blocking(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            diagnostics.mkdir(parents=True, exist_ok=True)
            (diagnostics / "managed_data_quality_scorecard.json").write_text(
                json.dumps({"status": "warning", "gate_passed": True, "blocking_reasons": [], "warning_reasons": ["basis_jump_outlier"]}),
                encoding="utf-8",
            )
            readiness = validate_v12_managed_readiness(
                health={"status": "ready", "provider_status": "success_with_required_fields", "v12_allowed": True, "blocking_reasons": []},
                audit={"status": "ready", "v12_allowed": True, "blocking_reasons": [], "leakage_checks": {"point_in_time_join_ready": True, "source_timestamp_leakage_pass": True, "asof_date_leakage_pass": True, "feature_date_cutoff_pass": True, "ingest_timestamp_not_used_as_asof_pass": True}},
                schema_mapping={"status": "ready", "schema_mapping_ready": True, "blocking_reasons": []},
                managed_rows=[
                    {
                        "feature_date": "2026-05-01",
                        "asof_date": "2026-05-01",
                        "source_timestamp": "2026-05-01T15:30:00",
                        "ingest_timestamp": "2026-05-01T16:00:00",
                        "prediction_cutoff_date": "2026-05-01",
                        "spot_price": 100,
                        "spot_premium": 1,
                        "spot_futures_basis": 2,
                        "shfe_inventory": 100,
                        "shfe_warehouse_receipt": 90,
                        "lme_tin_close": 101,
                        "lme_inventory": 50,
                        "near_contract_close": 99,
                        "near_open_interest": 1000,
                        "far_contract_close": 98,
                        "far_open_interest": 900,
                        "main_contract_switch_flag": 0,
                    }
                ],
            )

        self.assertIn("basis_jump_outlier", readiness["quality_warning_reasons"])
        self.assertNotIn("managed_data_quality:quality_warning", readiness["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
