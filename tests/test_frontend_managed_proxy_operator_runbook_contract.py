from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxyOperatorRunbookContractTest(unittest.TestCase):
    def test_frontend_api_exposes_operator_runbook_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ManagedProxyOperatorRunbookPayload", types)
        self.assertIn("getManagedProxyOperatorRunbook", terminal)
        self.assertIn("refreshManagedProxyOperatorRunbook", terminal)
        self.assertIn("/api/terminal/managed-proxy/operator-runbook", terminal)
        self.assertIn("/api/terminal/managed-proxy/refresh-operator-runbook", terminal)

    def test_data_status_page_renders_operator_runbook_without_raw_token_input(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Managed Proxy Operator Onboarding Runbook", page)
        self.assertIn("config methods", page)
        self.assertIn("env template status", page)
        self.assertIn("local config template status", page)
        self.assertIn("mapping template status", page)
        self.assertIn("gitignore coverage", page)
        self.assertIn("endpoint configured", page)
        self.assertIn("token configured", page)
        self.assertIn("safe setup steps", page)
        self.assertIn("Refresh operator runbook", page)
        self.assertNotIn('type="password"', page)
        self.assertNotIn("raw token input", page.lower())
        self.assertNotIn("SN_MANAGED_PROXY_TOKEN=", page)


if __name__ == "__main__":
    unittest.main()
