from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.settings_service import get_key_diagnostics, get_terminal_settings_status
from sn_futures.services.terminal_service import build_terminal_data_status
from sn_futures.services.tushare_futures_service import refresh_tushare_futures_data


class TushareTokenDiagnosticsTest(unittest.TestCase):
    def test_settings_and_key_diagnostics_return_only_masked_tushare_metadata(self) -> None:
        token = "ENV_TUSHARE_TOKEN_123456789"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": token}, clear=False):
            settings = get_terminal_settings_status()
            diagnostics = get_key_diagnostics()

        serialized = json.dumps({"settings": settings, "diagnostics": diagnostics}, ensure_ascii=False)
        self.assertTrue(settings["tushare_configured"])
        self.assertEqual(settings["tushare_source"], "env")
        self.assertIn("***", settings["tushare_masked"])
        self.assertTrue(diagnostics["tushare"]["configured"])
        self.assertEqual(diagnostics["tushare"]["source"], "env")
        self.assertIn("***", diagnostics["tushare"]["masked"])
        self.assertNotIn("value", diagnostics["tushare"])
        self.assertNotIn(token, serialized)

    def test_data_status_exposes_canonical_tushare_status_code(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": ""}, clear=False):
            refresh_tushare_futures_data(force=True)
            payload = build_terminal_data_status()

        sources = payload.get("sources", []) if isinstance(payload.get("sources"), list) else []
        tushare = next(item for item in sources if isinstance(item, dict) and item.get("provider_id") == "tushare")
        self.assertEqual(tushare["status"], "token_missing")
        self.assertEqual(tushare["row_count"], 0)


if __name__ == "__main__":
    unittest.main()
