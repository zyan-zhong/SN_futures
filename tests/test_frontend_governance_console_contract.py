from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendGovernanceConsoleContractTest(unittest.TestCase):
    def test_governance_console_page_and_route_exist(self) -> None:
        page = FRONTEND / "pages" / "GovernanceConsolePage.tsx"
        app = (FRONTEND / "App.tsx").read_text(encoding="utf-8")
        sidebar = (FRONTEND / "components" / "layout" / "SimpleSidebar.tsx").read_text(encoding="utf-8")

        self.assertTrue(page.exists())
        self.assertIn("GovernanceConsolePage", app)
        self.assertIn('"research-governance"', app)
        self.assertIn("Research Governance", sidebar)
        self.assertIn('"research-governance"', sidebar)

    def test_governance_console_aggregates_research_governance_widgets(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        for label in [
            "Research Decision Board",
            "Readiness DAG",
            "Evidence Freshness",
            "Evidence Bundle",
            "Run Ledger",
            "Hypothesis Registry",
            "Shadow Mode Readiness",
            "Model Registry Safety",
        ]:
            self.assertIn(label, page)

        self.assertIn("next_allowed_action", page)
        self.assertIn("blocked reasons", page)
        self.assertIn("forbidden actions", page)

    def test_governance_console_reuses_only_safe_report_endpoints(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        for helper in [
            "refreshResearchDecisionBoard",
            "refreshReadinessDag",
            "runSafeReadinessChecks",
            "refreshEvidenceFreshness",
            "refreshEvidenceBundle",
            "refreshRunLedger",
            "refreshAntiPHackingLedger",
            "refreshShadowModeReadiness",
            "refreshModelRegistrySafety",
        ]:
            self.assertIn(helper, page)

        for action_class in ["safe check", "report refresh", "heavy task", "forbidden action"]:
            self.assertIn(action_class, page)

    def test_governance_console_has_no_active_or_prediction_action_buttons(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")
        lower_page = page.lower()

        forbidden_helpers = [
            "approveActiveModel",
            "runCandidateV",
            "runModelExperiment",
            "buildFeatureStore",
            "buildTrainingDataset",
            "generateCustomerPrediction",
            "promoteCandidate",
        ]
        for helper in forbidden_helpers:
            self.assertNotIn(helper, page)

        forbidden_button_phrases = [
            "publish active",
            "approve active",
            "generate customer prediction",
            "run candidate",
            "train candidate",
            "build feature store",
            "build training dataset",
        ]
        for phrase in forbidden_button_phrases:
            self.assertNotIn(f">{phrase}<", lower_page)


if __name__ == "__main__":
    unittest.main()
