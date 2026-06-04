from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendResearchDecisionBoardContractTest(unittest.TestCase):
    def test_frontend_exposes_decision_board_api_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getResearchDecisionBoard", terminal)
        self.assertIn("refreshResearchDecisionBoard", terminal)
        self.assertIn("/api/terminal/research/decision-board", terminal)
        self.assertIn("/api/terminal/research/refresh-decision-board", terminal)
        self.assertIn("ResearchDecisionBoardPayload", types)
        self.assertIn("current_research_state", types)
        self.assertIn("next_allowed_action", types)
        self.assertIn("candidate_training_allowed", types)
        self.assertIn("active_publish_allowed", types)

    def test_model_research_page_renders_decision_board_card(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Research Decision Board", page)
        self.assertIn("current_research_state", page)
        self.assertIn("next_allowed_action", page)
        self.assertIn("candidate_training_allowed", page)
        self.assertIn("candidate_v12_allowed", page)
        self.assertIn("manual_approval_recommended", page)
        self.assertIn("active_publish_allowed", page)
        self.assertIn("top blocking reasons", page)
        self.assertIn("evidence paths", page)
        self.assertIn("stale/missing reports", page)


if __name__ == "__main__":
    unittest.main()
