from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendCandidateDiagnosticsContractTest(unittest.TestCase):
    def test_frontend_exposes_candidate_diagnostics_api(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        self.assertIn("/api/terminal/models/candidate-diagnostics", terminal)
        self.assertIn("getCandidateDiagnostics", terminal)

    def test_model_governance_shows_failure_attribution(self) -> None:
        page = (FRONTEND / "pages" / "ModelGovernancePage.tsx").read_text(encoding="utf-8")
        panel = (FRONTEND / "components" / "model" / "CandidateDiagnosticsPanel.tsx").read_text(encoding="utf-8")
        self.assertIn("CandidateDiagnosticsPanel", page)
        self.assertIn("Candidate 失败归因", panel)
        self.assertIn("不发布 active", panel)
        self.assertIn("不生成客户预测", panel)
        self.assertIn("高置信分层", panel)
        self.assertIn("校准问题", panel)


if __name__ == "__main__":
    unittest.main()
