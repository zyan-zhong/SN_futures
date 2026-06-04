from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxySetupContractTest(unittest.TestCase):
    def test_frontend_api_exposes_managed_proxy_setup_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ManagedProxySetupPayload", types)
        self.assertIn("getManagedProxySetup", terminal)
        self.assertIn("refreshManagedProxySetup", terminal)
        self.assertIn("getManagedProxyEndpointContract", terminal)
        self.assertIn("runManagedProxyContractDryRun", terminal)
        self.assertIn("/api/terminal/managed-proxy/setup", terminal)
        self.assertIn("/api/terminal/managed-proxy/run-contract-dry-run", terminal)

    def test_data_status_page_renders_setup_contract_card(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Managed Proxy Setup", page)
        self.assertIn("endpoint contract status", page)
        self.assertIn("schema contract status", page)
        self.assertIn("PIT timestamp contract status", page)
        self.assertIn("Refresh setup", page)
        self.assertIn("Run contract dry-run", page)


if __name__ == "__main__":
    unittest.main()
