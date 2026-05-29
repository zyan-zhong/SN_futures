from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.private_bundle_keys import import_private_bundle_keys_if_needed
from sn_futures.services.api_key_resolver import resolve_secret
from sn_futures.services.settings_service import reset_terminal_secrets


class PrivateBundleKeyPriorityTest(unittest.TestCase):
    def test_user_secret_is_not_overwritten_by_private_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "private_bundle_seed.json"
            seed.write_text(
                json.dumps(
                    {
                        "secrets": {
                            "SN_ALPHA_VANTAGE_KEY": "BUNDLE_ALPHA_PRIVATE_123",
                            "SN_NEWSAPI_KEY": "BUNDLE_NEWS_PRIVATE_123",
                        }
                    }
                ),
                encoding="utf-8",
            )
            secrets = Path(tmp) / "config" / "secrets.json"
            secrets.parent.mkdir(parents=True)
            secrets.write_text(
                json.dumps(
                    {
                        "SN_ALPHA_VANTAGE_KEY": "USER_ALPHA_PRIVATE_123",
                        "SN_NEWSAPI_KEY": "USER_NEWS_PRIVATE_123",
                        "_sources": {
                            "SN_ALPHA_VANTAGE_KEY": "user_secrets",
                            "SN_NEWSAPI_KEY": "user_secrets",
                        },
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_PRIVATE_BUNDLE_SEED": str(seed)}, clear=False):
                result = import_private_bundle_keys_if_needed()
                alpha = resolve_secret("SN_ALPHA_VANTAGE_KEY")
                news = resolve_secret("SN_NEWSAPI_KEY")

        self.assertEqual(result["imported"], [])
        self.assertEqual(alpha["source"], "user_secrets")
        self.assertEqual(alpha["value"], "USER_ALPHA_PRIVATE_123")
        self.assertEqual(news["source"], "user_secrets")
        self.assertEqual(news["value"], "USER_NEWS_PRIVATE_123")

    def test_reset_restores_private_bundle_when_seed_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "private_bundle_seed.json"
            seed.write_text(
                json.dumps(
                    {
                        "secrets": {
                            "SN_ALPHA_VANTAGE_KEY": "BUNDLE_ALPHA_PRIVATE_456",
                            "SN_NEWSAPI_KEY": "BUNDLE_NEWS_PRIVATE_456",
                        }
                    }
                ),
                encoding="utf-8",
            )
            with patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_PRIVATE_BUNDLE_SEED": str(seed)}, clear=False):
                result = reset_terminal_secrets()

        self.assertTrue(result["alpha_vantage_configured"])
        self.assertTrue(result["newsapi_configured"])
        self.assertEqual(result["alpha_vantage_source"], "private_bundle")
        self.assertEqual(result["newsapi_source"], "private_bundle")


if __name__ == "__main__":
    unittest.main()
