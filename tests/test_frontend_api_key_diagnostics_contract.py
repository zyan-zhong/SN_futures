from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendApiKeyDiagnosticsContractTest(unittest.TestCase):
    def test_settings_page_has_provider_test_buttons(self) -> None:
        text = (ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")
        self.assertIn("测试 Alpha Vantage", text)
        self.assertIn("测试 NewsAPI", text)
        self.assertIn("getKeyDiagnostics", text)
        self.assertNotIn("useLocalSetting(\"SN_ALPHA_VANTAGE_KEY", text)
        self.assertNotIn("useLocalSetting(\"SN_NEWSAPI_KEY", text)

    def test_terminal_client_exposes_key_diagnostics(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        settings = (ROOT / "frontend" / "src" / "api" / "settings.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn('from "./settings"', terminal)
        self.assertIn("getKeyDiagnostics", terminal)
        self.assertIn("/api/terminal/settings/key-diagnostics", settings)
        self.assertIn("alpha_vantage", types)


if __name__ == "__main__":
    unittest.main()
