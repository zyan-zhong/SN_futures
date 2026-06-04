from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendCostStressAttributionContractTest(unittest.TestCase):
    def test_frontend_exposes_cost_stress_attribution_api_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getCostStressAttribution", terminal)
        self.assertIn("refreshCostStressAttribution", terminal)
        self.assertIn("/api/terminal/research/cost-stress-attribution", terminal)
        self.assertIn("/api/terminal/research/refresh-cost-stress-attribution", terminal)
        self.assertIn("CostStressAttributionPayload", types)
        self.assertIn("CostStressAttributionEvidence", types)
        self.assertIn("turnover_diagnostics", types)
        self.assertIn("signal_flip_diagnostics", types)
        self.assertIn("holding_period_diagnostics", types)
        self.assertIn("failure_drivers", types)

    def test_model_research_page_renders_cost_stress_attribution_section(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Cost Stress Attribution", page)
        self.assertIn("Candidate v10 attribution status", page)
        self.assertIn("Candidate v12 attribution status", page)
        self.assertIn("by horizon", page)
        self.assertIn("by regime", page)
        self.assertIn("by year", page)
        self.assertIn("turnover diagnostics", page)
        self.assertIn("signal flip diagnostics", page)
        self.assertIn("holding period diagnostics", page)
        self.assertIn("failure drivers", page)
        self.assertIn("skipped reason", page)


if __name__ == "__main__":
    unittest.main()
