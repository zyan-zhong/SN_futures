from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendCandidateTrainingContractTest(unittest.TestCase):
    def test_terminal_client_exposes_candidate_training_apis(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        self.assertIn("/api/terminal/models/train-candidate", terminal)
        self.assertIn("/api/terminal/models/candidate-status", terminal)
        self.assertIn("/api/terminal/models/walk-forward-results", terminal)

    def test_model_governance_page_shows_candidate_not_active(self) -> None:
        page = (FRONTEND / "pages" / "ModelGovernancePage.tsx").read_text(encoding="utf-8")
        panel = (FRONTEND / "components" / "model" / "CandidateTrainingPanel.tsx").read_text(encoding="utf-8")
        self.assertIn("CandidateTrainingPanel", page)
        self.assertIn("候选模型不能替代 active", panel)
        self.assertIn("Promotion gate 未通过前不生成真实预测", panel)
        self.assertIn("不会进入客户预测页", panel)

    def test_prediction_page_does_not_show_baseline_customer_prediction(self) -> None:
        prediction = (FRONTEND / "pages" / "PredictionPage.tsx").read_text(encoding="utf-8").lower()
        self.assertNotIn("baseline forecast", prediction)
        self.assertNotIn("baseline backtest", prediction)
        self.assertNotIn("基线预测", prediction)
        self.assertNotIn("基线回测", prediction)


if __name__ == "__main__":
    unittest.main()
