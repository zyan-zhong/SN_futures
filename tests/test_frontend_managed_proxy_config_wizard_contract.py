from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxyConfigWizardContractTest(unittest.TestCase):
    def test_frontend_api_exposes_config_wizard_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ManagedProxyConfigWizardPayload", types)
        self.assertIn("getManagedProxyConfigWizard", terminal)
        self.assertIn("refreshManagedProxyConfigWizard", terminal)
        self.assertIn("/api/terminal/managed-proxy/config-wizard", terminal)
        self.assertIn("/api/terminal/managed-proxy/refresh-config-wizard", terminal)

    def test_data_status_page_renders_config_wizard_without_raw_token_input(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Managed Proxy Configuration Wizard", page)
        self.assertIn("safe configuration methods", page)
        self.assertIn("env template status", page)
        self.assertIn("local config template status", page)
        self.assertIn("gitignore secret coverage", page)
        self.assertIn("dry-run checklist", page)
        self.assertIn("Refresh wizard", page)
        self.assertNotIn('type="password"', page)
        self.assertNotIn("raw token", page.lower())


if __name__ == "__main__":
    unittest.main()
