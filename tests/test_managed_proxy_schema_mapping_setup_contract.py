from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_proxy_setup_service import run_managed_proxy_schema_dry_run


class AliasSetupClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        return {
            "status": "ok",
            "rows": [
                {
                    "ts_source": "2026-05-19T18:00:00",
                    "date_asof": "2026-05-19",
                    "ts_ingest": "2026-05-20T01:00:00",
                    "trade_day": "2026-05-20",
                    "cutoff_day": "2026-05-20",
                    "cash_px": 270000,
                    "premium": 100,
                    "basis": 80,
                    "inventory": 12000,
                    "receipt": 2000,
                    "lme_close": 33000,
                    "lme_stock": 4500,
                    "near_px": 270100,
                    "near_oi": 10000,
                    "far_px": 270800,
                    "far_oi": 8000,
                    "switch_flag": 0,
                }
            ],
        }


ALIAS_MAPPING = {
    "ts_source": "source_timestamp",
    "date_asof": "asof_date",
    "ts_ingest": "ingest_timestamp",
    "trade_day": "trading_date",
    "cutoff_day": "prediction_cutoff_date",
    "cash_px": "spot_price",
    "premium": "spot_premium",
    "basis": "spot_futures_basis",
    "inventory": "shfe_inventory",
    "receipt": "shfe_warehouse_receipt",
    "lme_close": "lme_tin_close",
    "lme_stock": "lme_inventory",
    "near_px": "near_contract_close",
    "near_oi": "near_open_interest",
    "far_px": "far_contract_close",
    "far_oi": "far_open_interest",
    "switch_flag": "main_contract_switch_flag",
}


class ManagedProxySchemaMappingSetupContractTest(unittest.TestCase):
    def _env(self, tmp: str) -> patch:
        return patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_MANAGED_PROXY_ENABLED": "true",
                "SN_MANAGED_PROXY_BASE_URL": "https://managed.example",
                "SN_MANAGED_PROXY_TOKEN": "managed-secret-token",
                "SN_MANAGED_DATA_PROXY_ENABLED": "",
                "SN_MANAGED_DATA_PROXY_URL": "",
                "SN_MANAGED_DATA_PROXY_TOKEN": "",
            },
            clear=False,
        )

    def test_setup_dry_run_applies_mapping_before_schema_validation_without_v12_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            mapping_path = Path(tmp) / "config" / "managed_proxy.mapping.local.json"
            mapping_path.parent.mkdir(parents=True, exist_ok=True)
            mapping_path.write_text(json.dumps({"field_mapping": ALIAS_MAPPING}), encoding="utf-8")

            report = run_managed_proxy_schema_dry_run(client=AliasSetupClient())
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["mapping_applied"])
        self.assertEqual(report["schema_mapping_status"], "ready")
        self.assertTrue(report["schema_mapping_ready"])
        self.assertEqual(report["missing_fields"], [])
        self.assertEqual(report["missing_timestamp_fields"], [])
        self.assertFalse(report["feature_store_v12_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertNotIn("managed-secret-token", serialized + report_text)


if __name__ == "__main__":
    unittest.main()
