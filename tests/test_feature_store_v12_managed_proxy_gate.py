from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v12_service import build_feature_store_v12


class FeatureStoreV12ManagedProxyGateTest(unittest.TestCase):
    def test_v12_build_is_blocked_when_managed_proxy_health_not_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_MANAGED_DATA_PROXY_TOKEN": "",
                "SN_MANAGED_DATA_PROXY_URL": "",
                "SN_MANAGED_DATA_PROXY_ENABLED": "",
            },
            clear=False,
        ):
            result = build_feature_store_v12()
            manifest_path = Path(result["manifest_path"])
            manifest_text = manifest_path.read_text(encoding="utf-8")

        self.assertEqual(result["version"], "v12")
        self.assertEqual(result["status"], "blocked")
        self.assertFalse(result["managed_proxy_readiness"]["v12_allowed"])
        self.assertIn("managed_proxy_disabled", result["managed_proxy_readiness"]["blocking_reasons"])
        self.assertTrue(result["no_fake_data"])
        self.assertFalse(result["active_model_written"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertNotIn("SN_MANAGED_DATA_PROXY_TOKEN", json.dumps(result, ensure_ascii=False))
        self.assertNotIn("SN_MANAGED_DATA_PROXY_TOKEN", manifest_text)


if __name__ == "__main__":
    unittest.main()
