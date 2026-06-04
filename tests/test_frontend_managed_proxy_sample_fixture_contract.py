from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxySampleFixtureContractTest(unittest.TestCase):
    def test_frontend_api_exposes_sample_fixture_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ManagedProxySampleFixturePayload", types)
        self.assertIn("getManagedProxySampleFixture", terminal)
        self.assertIn("importManagedProxySampleFixture", terminal)
        self.assertIn("runManagedProxySampleFixtureContractTests", terminal)
        self.assertIn("/api/terminal/managed-proxy/sample-fixture", terminal)
        self.assertIn("/api/terminal/managed-proxy/import-sample-fixture", terminal)
        self.assertIn("/api/terminal/managed-proxy/run-sample-fixture-contract-tests", terminal)

    def test_data_status_page_renders_sample_fixture_harness_without_raw_token_input(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Sample Fixture Contract Harness", page)
        self.assertIn("sample_data_used", page)
        self.assertIn("production_eligible", page)
        self.assertIn("schema_contract_status", page)
        self.assertIn("pit_replay_status", page)
        self.assertIn("data_quality_status", page)
        self.assertIn("sample fixture cannot unlock v12", page.lower())
        self.assertNotIn('type="password"', page)
        self.assertNotIn("raw token input", page.lower())


if __name__ == "__main__":
    unittest.main()
