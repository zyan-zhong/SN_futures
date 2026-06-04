from __future__ import annotations

import json
import os
import tempfile
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.provider_credentials_service import build_provider_credential_handoff


class ProviderCredentialsServiceTest(unittest.TestCase):
    def test_missing_provider_api_key_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            payload = build_provider_credential_handoff(write=False)

        self.assertEqual(payload["provider_mode"], "local_api_provider")
        self.assertEqual(payload["provider_credentials_status"], "missing_config")
        self.assertIn("twelvedata", payload["missing_provider_credentials"])
        self.assertIn("alphavantage", payload["missing_provider_credentials"])
        self.assertFalse(payload["feature_store_v12_allowed"])

    def test_configured_provider_key_is_masked_and_not_echoed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_TWELVEDATA_API_KEY": "td-secret-key-123456"},
            clear=True,
        ):
            payload = build_provider_credential_handoff(write=False)

        serialized = json.dumps(payload, ensure_ascii=False)
        self.assertIn("twelvedata", payload["configured_providers"])
        self.assertTrue(payload["providers"]["twelvedata"]["key_configured"])
        self.assertTrue(payload["providers"]["twelvedata"]["key_masked"])
        self.assertNotIn("td-secret-key-123456", serialized)
        self.assertIn("<paste-key-only-in-your-local-shell>", serialized)

    def test_yfinance_is_research_only_and_cannot_unlock_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            payload = build_provider_credential_handoff(write=False)

        yfinance = payload["providers"]["yfinance_research_only"]
        self.assertTrue(yfinance["research_only"])
        self.assertFalse(yfinance["production_eligible"])
        self.assertFalse(yfinance["realtime_guarantee"])
        self.assertFalse(yfinance["can_unlock_v12"])


if __name__ == "__main__":
    unittest.main()
