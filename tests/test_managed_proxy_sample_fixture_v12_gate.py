from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v12_service import validate_v12_managed_readiness
from sn_futures.services.managed_proxy_sample_fixture_service import run_fixture_contract_tests


def _write_fixture(path: Path) -> Path:
    rows = [
        {
            "source_timestamp": "2024-01-02T15:00:00",
            "asof_date": "2024-01-02",
            "ingest_timestamp": "2024-01-02T18:00:00",
            "feature_date": "2024-01-03",
            "prediction_cutoff_date": "2024-01-03",
            "spot_price": 205000,
            "spot_premium": 150,
            "spot_futures_basis": 120,
            "shfe_inventory": 4800,
            "shfe_warehouse_receipt": 3500,
            "lme_tin_close": 25200,
            "lme_inventory": 4100,
            "near_contract_close": 204880,
            "near_open_interest": 11000,
            "far_contract_close": 205300,
            "far_open_interest": 8700,
            "main_contract_switch_flag": 0,
        },
        {
            "source_timestamp": "2024-01-03T15:00:00",
            "asof_date": "2024-01-03",
            "ingest_timestamp": "2024-01-03T18:00:00",
            "feature_date": "2024-01-04",
            "prediction_cutoff_date": "2024-01-04",
            "spot_price": 206000,
            "spot_premium": 150,
            "spot_futures_basis": 180,
            "shfe_inventory": 4900,
            "shfe_warehouse_receipt": 3500,
            "lme_tin_close": 25200,
            "lme_inventory": 4100,
            "near_contract_close": 204880,
            "near_open_interest": 11000,
            "far_contract_close": 205300,
            "far_open_interest": 8700,
            "main_contract_switch_flag": 0,
        },
    ]
    path.write_text(__import__("json").dumps({"fixture_only": True, "rows": rows}), encoding="utf-8")
    return path


class ManagedProxySampleFixtureV12GateTest(unittest.TestCase):
    def test_sample_fixture_contract_pass_never_unlocks_feature_store_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            path = _write_fixture(Path(tmp) / "fixture.json")
            fixture_report = run_fixture_contract_tests(path)
            readiness = validate_v12_managed_readiness(managed_rows=[])

        self.assertEqual(fixture_report["status"], "ready")
        self.assertFalse(fixture_report["feature_store_v12_allowed"])
        self.assertEqual(readiness["status"], "blocked")
        self.assertFalse(readiness["v12_allowed"])
        self.assertIn("sample_fixture_not_production_data", readiness["blocking_reasons"])
        self.assertFalse(readiness["managed_data_used"])
        self.assertFalse(readiness["training_invoked"])
        self.assertFalse(readiness["active_updated"])
        self.assertFalse(readiness["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
