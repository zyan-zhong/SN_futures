from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_proxy_schema_mapper_service import (
    apply_field_mapping_to_sample_rows,
    build_schema_mapping_report,
    refresh_schema_mapping_report,
)


def canonical_row() -> dict:
    return {
        "source_timestamp": "2026-05-19T18:00:00",
        "asof_date": "2026-05-19",
        "ingest_timestamp": "2026-05-20T01:00:00",
        "feature_date": "2026-05-20",
        "prediction_cutoff_date": "2026-05-20",
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


ALIAS_MAPPING = {
    "source_ts": "source_timestamp",
    "asof": "asof_date",
    "ingested_at": "ingest_timestamp",
    "trade_day": "feature_date",
    "cutoff": "prediction_cutoff_date",
    "spot_px": "spot_price",
    "premium": "spot_premium",
    "basis": "spot_futures_basis",
    "inventory": "shfe_inventory",
    "warehouse": "shfe_warehouse_receipt",
    "lme_close": "lme_tin_close",
    "lme_stock": "lme_inventory",
    "near_close": "near_contract_close",
    "near_oi": "near_open_interest",
    "far_close": "far_contract_close",
    "far_oi": "far_open_interest",
    "switch_flag": "main_contract_switch_flag",
}


def alias_row() -> dict:
    base = canonical_row()
    return {provider: base[canonical] for provider, canonical in ALIAS_MAPPING.items()}


class ManagedProxySchemaMappingServiceTest(unittest.TestCase):
    def _env(self, tmp: str) -> patch:
        return patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_INSIGHT_DATA_DIR": "",
                "SN_MANAGED_PROXY_TOKEN": "",
                "SN_MANAGED_PROXY_BASE_URL": "",
            },
            clear=False,
        )

    def test_same_name_fields_pass_without_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            report = build_schema_mapping_report(sample_rows=[canonical_row()])

        self.assertEqual(report["status"], "ready")
        self.assertFalse(report["mapping_applied"])
        self.assertTrue(report["schema_mapping_ready"])
        self.assertEqual(report["unmapped_required_fields"], [])
        self.assertEqual(report["timestamp_mapping_status"], "pass")
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_complete_alias_mapping_passes_and_maps_rows_without_mutating_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            original = alias_row()
            mapped = apply_field_mapping_to_sample_rows([original], ALIAS_MAPPING)
            report = build_schema_mapping_report(sample_rows=[original], field_mapping=ALIAS_MAPPING)

        self.assertEqual(report["status"], "ready")
        self.assertTrue(report["mapping_applied"])
        self.assertEqual(report["unmapped_required_fields"], [])
        self.assertIn("spot_price", mapped[0])
        self.assertNotIn("spot_price", original)
        self.assertEqual(original["spot_px"], 270000)

    def test_ambiguous_duplicate_missing_and_timestamp_mapping_fail(self) -> None:
        cases = [
            ({"provider_one": ["spot_price", "spot_premium"]}, "ambiguous_field_mapping"),
            ({"p1": "spot_price", "p2": "spot_price"}, "duplicate_canonical_targets"),
            ({**ALIAS_MAPPING, "missing_provider": "spot_price"}, "mapping_provider_field_missing"),
            ({k: v for k, v in ALIAS_MAPPING.items() if v != "source_timestamp"}, "canonical_timestamp_fields_missing"),
        ]
        for mapping, reason in cases:
            with self.subTest(reason=reason), tempfile.TemporaryDirectory() as tmp, self._env(tmp):
                report = build_schema_mapping_report(sample_rows=[alias_row()], field_mapping=mapping)

            self.assertEqual(report["status"], "blocked")
            self.assertFalse(report["schema_mapping_ready"])
            self.assertIn(reason, report["blocking_reasons"])

    def test_local_mapping_file_is_ignored_template_only_and_report_has_no_secret(self) -> None:
        root = Path(__file__).resolve().parents[1]
        gitignore = (root / ".gitignore").read_text(encoding="utf-8")
        example = (root / "config" / "managed_proxy.mapping.example.json").read_text(encoding="utf-8")
        self.assertIn("config/managed_proxy.mapping.local.json", gitignore)
        self.assertIn("field_mapping", example)

        with tempfile.TemporaryDirectory() as tmp, self._env(tmp), patch.dict(
            os.environ,
            {"SN_MANAGED_PROXY_TOKEN": "managed-secret-token", "SN_MANAGED_PROXY_BASE_URL": "https://managed.example"},
            clear=False,
        ):
            report = refresh_schema_mapping_report(sample_rows=[canonical_row()])
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertNotIn("managed-secret-token", serialized)
        self.assertNotIn("managed-secret-token", report_text)
        self.assertFalse(report["fake_data_used"])


if __name__ == "__main__":
    unittest.main()
