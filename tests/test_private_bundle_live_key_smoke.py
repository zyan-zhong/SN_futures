from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.private_bundle_keys import import_private_bundle_keys_if_needed


FAKE_ALPHA = "FAKE_ALPHA_LIVE_SMOKE_123456"
FAKE_NEWS = "FAKE_NEWS_LIVE_SMOKE_123456"


class PrivateBundleLiveKeySmokeTest(unittest.TestCase):
    def test_private_bundle_import_makes_settings_and_registry_configured(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            seed = Path(tmp) / "private_bundle_seed.json"
            seed.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source": "private_bundle",
                        "secrets": {
                            "SN_ALPHA_VANTAGE_KEY": FAKE_ALPHA,
                            "SN_NEWSAPI_KEY": FAKE_NEWS,
                        },
                    }
                ),
                encoding="utf-8",
            )
            env = {
                "SN_DATA_DIR": tmp,
                "SN_PRIVATE_BUNDLE_SEED": str(seed),
                "SN_ALPHA_VANTAGE_KEY": "",
                "SN_NEWSAPI_KEY": "",
            }
            with patch.dict(os.environ, env, clear=False):
                os.environ.pop("SN_ALPHA_VANTAGE_KEY", None)
                os.environ.pop("SN_NEWSAPI_KEY", None)
                imported = import_private_bundle_keys_if_needed()
                status_code, settings = handle_terminal_api("/api/terminal/settings/status", "GET")
                diag_code, diagnostics = handle_terminal_api("/api/terminal/settings/key-diagnostics", "GET")
                registry_code, registry = handle_terminal_api("/api/terminal/online-data-sources/status", "GET")

        dumped = json.dumps({"settings": settings, "diagnostics": diagnostics, "registry": registry}, ensure_ascii=False)
        self.assertTrue(imported["available"])
        self.assertEqual(status_code, 200)
        self.assertEqual(diag_code, 200)
        self.assertEqual(registry_code, 200)
        self.assertTrue(settings["alpha_vantage_configured"])
        self.assertTrue(settings["newsapi_configured"])
        self.assertIn(settings["alpha_vantage_source"], {"private_bundle", "user_secrets"})
        self.assertIn(settings["newsapi_source"], {"private_bundle", "user_secrets"})
        self.assertTrue(diagnostics["alpha_vantage"]["can_read"])
        self.assertTrue(diagnostics["newsapi"]["can_read"])
        self.assertNotIn(FAKE_ALPHA, dumped)
        self.assertNotIn(FAKE_NEWS, dumped)
        statuses = {row["source_id"]: row["status"] for row in registry["sources"]}
        self.assertNotEqual(statuses["alphavantage_fx_macro"], "key_missing")
        self.assertNotEqual(statuses["newsapi_events"], "key_missing")


if __name__ == "__main__":
    unittest.main()
