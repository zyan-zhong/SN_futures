from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendShadowOutputContractTest(unittest.TestCase):
    def test_frontend_exposes_shadow_output_contract_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getShadowOutputContract", terminal)
        self.assertIn("refreshShadowOutputContract", terminal)
        self.assertIn("buildShadowOutputDryRun", terminal)
        self.assertIn("/api/terminal/governance/shadow-output-contract", terminal)
        self.assertIn("/api/terminal/governance/refresh-shadow-output-contract", terminal)
        self.assertIn("/api/terminal/governance/build-shadow-output-dry-run", terminal)
        self.assertIn("ShadowOutputContractPayload", types)
        self.assertIn("shadow_output_allowed", types)
        self.assertIn("dry_run_artifact_created", types)

    def test_governance_console_renders_shadow_output_contract_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Shadow Output Contract", page)
        self.assertIn("shadow output allowed", page)
        self.assertIn("dry-run artifact status", page)
        self.assertIn("output root", page)
        self.assertIn("path isolation", page)
        self.assertIn("schema validation", page)
        self.assertIn("customer prediction collision status", page)

    def test_governance_console_does_not_expose_real_shadow_or_customer_prediction_buttons(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8").lower()

        self.assertNotIn(">build real shadow output<", page)
        self.assertNotIn(">generate customer prediction<", page)
        self.assertNotIn(">publish active<", page)


if __name__ == "__main__":
    unittest.main()
