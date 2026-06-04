from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendV10RemediationPreflightContractTest(unittest.TestCase):
    def test_frontend_exposes_preflight_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getV10RemediationPreflight", terminal)
        self.assertIn("refreshV10RemediationPreflight", terminal)
        self.assertIn("/api/terminal/research/v10-remediation-preflight", terminal)
        self.assertIn("/api/terminal/research/refresh-v10-remediation-preflight", terminal)
        self.assertIn("CandidateV10RemediationPreflightPayload", types)
        self.assertIn("recommended_experiment_order", types)
        self.assertIn("metric_budget_status", types)
        self.assertIn("overfitting_risk", types)

    def test_model_research_page_renders_remediation_preflight_card(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Remediation Preflight", page)
        self.assertIn("preflight status", page)
        self.assertIn("recommended experiments", page)
        self.assertIn("overfitting risk", page)
        self.assertIn("blocked experiments", page)
        self.assertIn("Refresh preflight", page)


if __name__ == "__main__":
    unittest.main()
