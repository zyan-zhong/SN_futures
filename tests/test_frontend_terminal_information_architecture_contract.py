from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendTerminalInformationArchitectureContractTest(unittest.TestCase):
    def test_research_lab_has_current_state_and_prediction_workspace_first_class_sections(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")
        api = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getPredictionWorkspaceStatus", api)
        self.assertIn("PredictionWorkspaceStatusPayload", types)
        self.assertIn("Current State", page)
        self.assertIn("Prediction Workspace", page)
        self.assertIn("prediction_status", page)
        self.assertIn("active_model_available", page)
        self.assertIn("active_publish_allowed", page)
        self.assertIn("customer_prediction_generated", page)
        self.assertIn("next_allowed_action", page)
        self.assertIn("no customer-visible output", page)

    def test_archived_candidates_are_collapsed_by_default(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Archived Candidates", page)
        self.assertIn("<details", page)
        self.assertNotIn("<details open", page)
        for candidate in ["candidate_v3", "candidate_v4", "candidate_v6", "candidate_v7", "candidate_v8", "candidate_v9"]:
            self.assertIn(candidate, page)
        self.assertIn("research-only archive", page)

    def test_no_customer_prediction_or_available_active_publish_button(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")
        lower = page.lower()

        self.assertNotIn(">generate customer prediction<", lower)
        self.assertNotIn(">生成客户预测<", page)
        self.assertNotIn("refreshPredictions", page)
        self.assertNotIn("getPredictions", page)
        self.assertNotIn('className="primary-button" type="button" onClick={handleApproveActive}', page)
        self.assertIn("active publish unavailable", lower)


if __name__ == "__main__":
    unittest.main()
