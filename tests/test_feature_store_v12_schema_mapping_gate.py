from __future__ import annotations

import unittest

import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v12_service import validate_v12_managed_readiness


def complete_managed_row() -> dict:
    return {
        "feature_date": "2026-05-20",
        "prediction_cutoff_date": "2026-05-20",
        "source_timestamp": "2026-05-19T18:00:00",
        "asof_date": "2026-05-19",
        "ingest_timestamp": "2026-05-20T01:00:00",
        "spot_price": 270000,
        "spot_premium": 100,
        "spot_futures_basis": 80,
        "shfe_inventory": 12000,
        "shfe_warehouse_receipt": 2000,
        "lme_tin_close": 33000,
        "lme_inventory": 4500,
        "near_contract_close": 270100,
        "near_open_interest": 10000,
        "far_contract_close": 270800,
        "far_open_interest": 8000,
        "main_contract_switch_flag": 0,
    }


class FeatureStoreV12SchemaMappingGateTest(unittest.TestCase):
    def test_v12_readiness_requires_schema_mapping_pass(self) -> None:
        readiness = validate_v12_managed_readiness(
            health={"status": "ready", "provider_status": "success_with_required_fields", "v12_allowed": True, "blocking_reasons": []},
            audit={"status": "ready", "v12_allowed": True, "blocking_reasons": [], "leakage_checks": {"point_in_time_join_ready": True}},
            schema_mapping={"status": "blocked", "schema_mapping_ready": False, "blocking_reasons": ["canonical_timestamp_fields_missing"]},
            managed_rows=[complete_managed_row()],
        )

        self.assertEqual(readiness["status"], "blocked")
        self.assertFalse(readiness["v12_allowed"])
        self.assertFalse(readiness["schema_mapping_ready"])
        self.assertIn("canonical_timestamp_fields_missing", readiness["blocking_reasons"])
        self.assertIn("managed_proxy_schema_mapping_blocked", readiness["blocking_reasons"])
        self.assertFalse(readiness["training_invoked"])
        self.assertFalse(readiness["active_updated"])
        self.assertFalse(readiness["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
