from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxyHealthContractTest(unittest.TestCase):
    def test_frontend_api_exposes_managed_proxy_health_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getManagedProxyHealth", terminal)
        self.assertIn("checkManagedProxyHealth", terminal)
        self.assertIn("getManagedProxyReadiness", terminal)
        self.assertIn("/api/terminal/managed-proxy/health", terminal)
        self.assertIn("/api/terminal/managed-proxy/check", terminal)
        self.assertIn("/api/terminal/managed-proxy/readiness", terminal)
        self.assertIn("ManagedProxyHealthPayload", types)
        self.assertIn("v12_allowed", types)

    def test_data_status_page_renders_proxy_health_card(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Managed Data / Proxy Health", page)
        self.assertIn("required field coverage", page)
        self.assertIn("next allowed action", page)
        self.assertIn("blocking reasons", page)
        self.assertIn("token masked", page)


if __name__ == "__main__":
    unittest.main()
