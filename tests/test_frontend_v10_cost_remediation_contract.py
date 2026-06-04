from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendV10CostRemediationContractTest(unittest.TestCase):
    def test_frontend_exposes_v10_cost_remediation_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getV10CostRemediation", terminal)
        self.assertIn("refreshV10CostRemediation", terminal)
        self.assertIn("/api/terminal/research/v10-cost-remediation", terminal)
        self.assertIn("/api/terminal/research/refresh-v10-cost-remediation", terminal)
        self.assertIn("V10CostRemediationPayload", types)
        self.assertIn("no_train_counterfactuals", types)
        self.assertIn("manual_approval_recommended", types)

    def test_model_research_page_renders_research_only_sandbox(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Cost Failure Remediation Sandbox", page)
        self.assertIn("research_only", page)
        self.assertIn("recommended next experiment", page)
        self.assertIn("manual approval unchanged", page)
        self.assertIn("Refresh remediation sandbox", page)


if __name__ == "__main__":
    unittest.main()
