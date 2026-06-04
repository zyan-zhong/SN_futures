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
from sn_futures.services.settings_service import get_key_diagnostics, get_terminal_settings_status, save_terminal_secrets


class TushareKeyResolverTest(unittest.TestCase):
    def test_tushare_token_can_be_read_from_user_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            path = Path(tmp) / "config" / "secrets.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps({"SN_TUSHARE_TOKEN": "USER_TUSHARE_TOKEN_123456"}), encoding="utf-8")

            resolved = resolve_secret("SN_TUSHARE_TOKEN")

        self.assertTrue(resolved["configured"])
        self.assertEqual(resolved["source"], "user_secrets")
        self.assertEqual(resolved["value"], "USER_TUSHARE_TOKEN_123456")

    def test_tushare_token_can_be_read_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "ENV_TUSHARE_TOKEN_123456"},
            clear=False,
        ):
            resolved = resolve_secret("SN_TUSHARE_TOKEN")

        self.assertTrue(resolved["configured"])
        self.assertEqual(resolved["source"], "env")

    def test_tushare_token_missing_status_is_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": ""}, clear=False):
            resolved = resolve_secret("SN_TUSHARE_TOKEN")

        self.assertFalse(resolved["configured"])
        self.assertEqual(resolved["source"], "none")

    def test_settings_status_and_diagnostics_include_masked_tushare(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            saved = save_terminal_secrets({"SN_TUSHARE_TOKEN": "USER_TUSHARE_TOKEN_123456"})
            status = get_terminal_settings_status()
            diagnostics = get_key_diagnostics()

        self.assertTrue(saved["success"])
        self.assertTrue(status["tushare_configured"])
        self.assertEqual(status["tushare_source"], "user_secrets")
        self.assertIn("***", status["tushare_masked"])
        self.assertTrue(diagnostics["tushare"]["configured"])
        self.assertNotIn("USER_TUSHARE_TOKEN_123456", json.dumps(status))
        self.assertNotIn("USER_TUSHARE_TOKEN_123456", json.dumps(diagnostics))


if __name__ == "__main__":
    unittest.main()
