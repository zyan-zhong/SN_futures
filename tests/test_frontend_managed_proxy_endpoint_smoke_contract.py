from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxyEndpointSmokeContractTest(unittest.TestCase):
    def test_frontend_api_exposes_endpoint_smoke_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ManagedProxyEndpointSmokePayload", types)
        self.assertIn("getManagedProxyEndpointSmoke", terminal)
        self.assertIn("runManagedProxyEndpointSmoke", terminal)
        self.assertIn("/api/terminal/managed-proxy/endpoint-smoke", terminal)
        self.assertIn("/api/terminal/managed-proxy/run-endpoint-smoke", terminal)

    def test_data_status_page_renders_endpoint_smoke_card_without_raw_token_input(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Endpoint Smoke Test", page)
        self.assertIn("auth_status", page)
        self.assertIn("endpoint_reachable", page)
        self.assertIn("response_format_status", page)
        self.assertIn("token_echo_status", page)
        self.assertIn("raw_rows_persisted", page)
        self.assertIn("feature_store_v12_allowed", page)
        self.assertIn("Run endpoint smoke", page)
        self.assertNotIn('type="password"', page)
        self.assertNotIn("raw token input", page.lower())


if __name__ == "__main__":
    unittest.main()
