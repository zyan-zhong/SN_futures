from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v12_service import build_feature_store_v12, validate_v12_managed_readiness


READY_HEALTH = {
    "status": "ready",
    "provider_status": "success_with_required_fields",
    "v12_allowed": True,
    "blocking_reasons": [],
    "required_field_coverage": {"total": 12, "available": 12, "missing": 0, "ratio": 1.0, "label": "12/12"},
}

READY_AUDIT = {
    "status": "ready",
    "ready": True,
    "v12_allowed": True,
    "blocking_reasons": [],
    "missing_timestamp_fields": [],
    "missing_fundamental_fields": [],
    "field_timestamp_coverage": {"complete_ratio": 1.0, "by_field": {}},
    "leakage_checks": {
        "source_timestamp_leakage_pass": True,
        "asof_date_leakage_pass": True,
        "feature_date_cutoff_pass": True,
        "ingest_timestamp_not_used_as_asof_pass": True,
        "point_in_time_join_ready": True,
    },
}


class FeatureStoreV12BlockedFirstTest(unittest.TestCase):
    def test_disabled_health_writes_complete_blocked_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.feature_store_v12_service.load_latest_managed_health",
            return_value={
                "status": "blocked",
                "provider_status": "disabled",
                "v12_allowed": False,
                "blocking_reasons": ["managed_proxy_disabled"],
            },
        ), patch(
            "sn_futures.services.feature_store_v12_service.load_latest_managed_audit",
            return_value={"status": "blocked", "blocking_reasons": ["managed_proxy_disabled"]},
        ):
            result = build_feature_store_v12()
            manifest = json.loads(Path(result["manifest_path"]).read_text(encoding="utf-8"))

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(manifest["feature_store_version"], "v12")
        self.assertEqual(manifest["health_status"], "disabled")
        self.assertEqual(manifest["audit_status"], "blocked")
        self.assertFalse(manifest["managed_data_used"])
        self.assertFalse(manifest["fake_data_used"])
        self.assertFalse(manifest["mock_data_used"])
        self.assertFalse(manifest["training_invoked"])
        self.assertFalse(manifest["active_updated"])
        self.assertFalse(manifest["customer_prediction_generated"])
        self.assertIn("managed_proxy_disabled", manifest["blocking_reasons"])
        self.assertIn("required_timestamp_fields", manifest)
        self.assertIn("required_fundamental_fields", manifest)
        self.assertIn("managed_field_coverage", manifest)
        self.assertIn("technical_feature_coverage", manifest)
        self.assertFalse(manifest["point_in_time_join_ready"])
        self.assertFalse(manifest["no_lookahead_pass"])

    def test_token_missing_blocks_v12_readiness(self) -> None:
        readiness = validate_v12_managed_readiness(
            health={
                "status": "blocked",
                "provider_status": "token_missing",
                "v12_allowed": False,
                "blocking_reasons": ["managed_proxy_token_missing"],
            },
            audit=READY_AUDIT,
            managed_rows=[],
        )

        self.assertEqual(readiness["status"], "blocked")
        self.assertFalse(readiness["v12_allowed"])
        self.assertIn("managed_proxy_token_missing", readiness["blocking_reasons"])

    def test_missing_pit_audit_blocks_even_when_health_ready(self) -> None:
        readiness = validate_v12_managed_readiness(
            health=READY_HEALTH,
            audit={},
            managed_rows=[],
        )

        self.assertEqual(readiness["status"], "blocked")
        self.assertIn("managed_audit_missing", readiness["blocking_reasons"])

    def test_missing_required_timestamp_fields_block(self) -> None:
        rows = [
            {
                "feature_date": "2026-01-03",
                "source_timestamp": "2026-01-02",
                "ingest_timestamp": "2026-01-04",
                "prediction_cutoff_date": "2026-01-03",
            }
        ]
        readiness = validate_v12_managed_readiness(health=READY_HEALTH, audit=READY_AUDIT, managed_rows=rows)

        self.assertEqual(readiness["status"], "blocked")
        self.assertIn("missing_asof_date", readiness["blocking_reasons"])
        self.assertIn("asof_date", readiness["missing_timestamp_fields"])

    def test_missing_required_fundamental_fields_block(self) -> None:
        rows = [
            {
                "feature_date": "2026-01-03",
                "source_timestamp": "2026-01-02",
                "asof_date": "2026-01-02",
                "ingest_timestamp": "2026-01-04",
                "prediction_cutoff_date": "2026-01-03",
                "spot_price": 210000,
            }
        ]
        readiness = validate_v12_managed_readiness(health=READY_HEALTH, audit=READY_AUDIT, managed_rows=rows)

        self.assertEqual(readiness["status"], "blocked")
        self.assertIn("managed_fundamental_fields_missing", readiness["blocking_reasons"])
        self.assertIn("lme_inventory", readiness["missing_fundamental_fields"])

    def test_blocked_manifest_does_not_contain_sensitive_literals(self) -> None:
        secret = "secret-managed-token-123456"
        endpoint = "https://proxy.example.com/private/path?token=secret-managed-token-123456"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.feature_store_v12_service.load_latest_managed_health",
            return_value={
                "status": "blocked",
                "provider_status": "token_missing",
                "v12_allowed": False,
                "token_masked": "se***56",
                "endpoint": endpoint,
                "Authorization": f"Bearer {secret}",
                "blocking_reasons": ["managed_proxy_token_missing"],
            },
        ), patch(
            "sn_futures.services.feature_store_v12_service.load_latest_managed_audit",
            return_value={"status": "blocked", "blocking_reasons": ["managed_proxy_token_missing"]},
        ):
            result = build_feature_store_v12()
            text = Path(result["manifest_path"]).read_text(encoding="utf-8")

        self.assertNotIn(secret, text)
        self.assertNotIn("Authorization", text)
        self.assertNotIn(endpoint, text)


if __name__ == "__main__":
    unittest.main()
