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
from sn_futures.services.settings_service import get_key_diagnostics, save_terminal_secrets


class ApiKeyDiagnosticsTest(unittest.TestCase):
    def test_settings_secrets_save_sets_configured_and_diagnostics_masked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            os.environ.pop("SN_ALPHA_VANTAGE_KEY", None)
            result = save_terminal_secrets({"SN_ALPHA_VANTAGE_KEY": "USER_ALPHA_1234567890"})
            diagnostics = get_key_diagnostics()

        self.assertTrue(result["alpha_vantage_configured"])
        self.assertTrue(diagnostics["alpha_vantage"]["configured"])
        dumped = json.dumps(diagnostics, ensure_ascii=False)
        self.assertNotIn("USER_ALPHA_1234567890", dumped)
        self.assertEqual(diagnostics["alpha_vantage"]["source"], "user_secrets")

    def test_key_diagnostics_endpoint_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/settings/key-diagnostics", "GET", {}, None)

        self.assertEqual(status, 200)
        self.assertIn("alpha_vantage", payload)
        self.assertIn("newsapi", payload)
        self.assertNotIn("value", payload["alpha_vantage"])


if __name__ == "__main__":
    unittest.main()

