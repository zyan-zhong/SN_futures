from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendGovernanceMaturityMatrixContractTest(unittest.TestCase):
    def test_frontend_exposes_maturity_matrix_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getGovernanceMaturityMatrix", terminal)
        self.assertIn("refreshGovernanceMaturityMatrix", terminal)
        self.assertIn("/api/terminal/governance/maturity-matrix", terminal)
        self.assertIn("/api/terminal/governance/refresh-maturity-matrix", terminal)
        self.assertIn("GovernanceMaturityMatrixPayload", types)
        self.assertIn("domain_scores", types)
        self.assertIn("recommended_prompt_sequence", types)

    def test_governance_console_renders_maturity_gap_matrix_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Maturity Gap Matrix", page)
        self.assertIn("production_readiness", page)
        self.assertIn("shadow_readiness", page)
        self.assertIn("lowest scoring domains", page)
        self.assertIn("critical gaps", page)
        self.assertIn("completed controls", page)
        self.assertIn("missing controls", page)
        self.assertIn("recommended prompt sequence", page)
        self.assertIn("Refresh maturity matrix", page)

    def test_governance_console_does_not_expose_heavy_or_forbidden_controls(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8").lower()

        self.assertNotIn(">build feature store v12<", page)
        self.assertNotIn(">build training dataset v12<", page)
        self.assertNotIn(">run candidate v12<", page)
        self.assertNotIn(">publish active<", page)
        self.assertNotIn(">generate customer prediction<", page)


if __name__ == "__main__":
    unittest.main()
