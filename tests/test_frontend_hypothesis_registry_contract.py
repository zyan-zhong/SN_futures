from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendHypothesisRegistryContractTest(unittest.TestCase):
    def test_frontend_exposes_hypothesis_registry_api_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getHypothesisRegistry", terminal)
        self.assertIn("createHypothesisTemplate", terminal)
        self.assertIn("refreshAntiPHackingLedger", terminal)
        self.assertIn("/api/terminal/research/hypothesis-registry", terminal)
        self.assertIn("/api/terminal/research/create-hypothesis-template", terminal)
        self.assertIn("/api/terminal/research/refresh-anti-p-hacking-ledger", terminal)
        self.assertIn("HypothesisRegistryPayload", types)
        self.assertIn("AntiPHackingLedgerPayload", types)
        self.assertIn("p_hacking_risk_level", types)
        self.assertIn("experiment_budget_by_blocker", types)

    def test_model_research_page_renders_hypothesis_registry_section(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Hypothesis Registry", page)
        self.assertIn("open hypotheses", page)
        self.assertIn("linked blockers", page)
        self.assertIn("p-hacking risk", page)
        self.assertIn("experiment budget usage", page)
        self.assertIn("Refresh ledger", page)


if __name__ == "__main__":
    unittest.main()
