from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxyQuarantineContractTest(unittest.TestCase):
    def test_frontend_api_exposes_quarantine_contract_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ManagedProxyQuarantineContractPayload", types)
        self.assertIn("getManagedProxyQuarantineContract", terminal)
        self.assertIn("runManagedProxyQuarantineContract", terminal)
        self.assertIn("promoteQuarantineToResearchCache", terminal)
        self.assertIn("/api/terminal/managed-proxy/quarantine-contract", terminal)
        self.assertIn("/api/terminal/managed-proxy/run-quarantine-contract", terminal)
        self.assertIn("/api/terminal/managed-proxy/promote-quarantine-to-research-cache", terminal)

    def test_data_status_page_renders_quarantine_contract_gate_without_secret_or_output_inputs(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Quarantine Contract / Research Cache Gate", page)
        self.assertIn("schema_contract_status", page)
        self.assertIn("pit_replay_status", page)
        self.assertIn("pit_audit_status", page)
        self.assertIn("data_quality_status", page)
        self.assertIn("research cache allowed", page.lower())
        self.assertIn("research cache written", page.lower())
        self.assertIn("production_eligible", page)
        self.assertIn("feature_store_v12_allowed", page)
        self.assertIn("v12 still blocked", page.lower())
        self.assertIn("Run quarantine contract", page)
        self.assertIn("Promote to research cache", page)
        self.assertNotIn('type="password"', page)
        self.assertNotIn("raw token input", page.lower())
        self.assertNotIn("custom output path", page.lower())


if __name__ == "__main__":
    unittest.main()
