from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.api_key_resolver import resolve_secret


class SettingsKeySourcePriorityTest(unittest.TestCase):
    def test_env_example_declares_canonical_local_api_provider_names(self) -> None:
        env_example = Path(".env.example").read_text(encoding="utf-8")
        expected = {
            "SN_ALPHA_VANTAGE_KEY",
            "SN_NEWSAPI_KEY",
            "SN_TUSHARE_TOKEN",
            "SN_LOCAL_API_PROVIDER_ENABLED",
            "SN_LOCAL_API_PROVIDER_ID",
            "SN_LOCAL_API_PROVIDER_BASE_URL",
            "SN_LOCAL_API_PROVIDER_TOKEN",
        }

        for name in expected:
            self.assertIn(f"{name}=", env_example)

        self.assertNotIn("SN_MANAGED_PROXY_TOKEN=", env_example)
        self.assertNotIn("SN_MANAGED_DATA_PROXY_TOKEN=", env_example)
        self.assertEqual(resolve_secret("SN_LOCAL_API_PROVIDER_TOKEN")["name"], "SN_LOCAL_API_PROVIDER_TOKEN")

    def test_environment_key_can_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_ALPHA_VANTAGE_KEY": "ENV_ALPHA_1234567890"}, clear=False):
            resolved = resolve_secret("SN_ALPHA_VANTAGE_KEY")

        self.assertTrue(resolved["configured"])
        self.assertEqual(resolved["source"], "env")

    def test_user_secrets_take_priority_over_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_ALPHA_VANTAGE_KEY": "ENV_ALPHA_1234567890"}, clear=False):
            path = Path(tmp) / "config" / "secrets.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"SN_ALPHA_VANTAGE_KEY": "USER_ALPHA_1234567890"}), encoding="utf-8")
            resolved = resolve_secret("SN_ALPHA_VANTAGE_KEY")

        self.assertEqual(resolved["source"], "user_secrets")
        self.assertEqual(resolved["value"], "USER_ALPHA_1234567890")

    def test_legacy_managed_proxy_token_is_compatible_but_deprecated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_MANAGED_PROXY_TOKEN": "LEGACY_MANAGED_TOKEN_1234567890"},
            clear=True,
        ):
            resolved = resolve_secret("SN_LOCAL_API_PROVIDER_TOKEN")

        self.assertTrue(resolved["configured"])
        self.assertEqual(resolved["name"], "SN_LOCAL_API_PROVIDER_TOKEN")
        self.assertEqual(resolved["resolved_name"], "SN_MANAGED_PROXY_TOKEN")
        self.assertTrue(resolved["deprecated"])
        self.assertIn("SN_LOCAL_API_PROVIDER_TOKEN", resolved["deprecated_warning"])


if __name__ == "__main__":
    unittest.main()
