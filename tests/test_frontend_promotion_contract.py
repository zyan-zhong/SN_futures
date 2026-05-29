from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendPromotionContractTest(unittest.TestCase):
    def test_frontend_exposes_promotion_apis(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        self.assertIn("/api/terminal/models/promote-candidate", terminal)
        self.assertIn("/api/terminal/models/active-status", terminal)
        self.assertIn("/api/terminal/models/promotion-report", terminal)

    def test_promotion_panel_shows_failure_reason_and_candidate_guard(self) -> None:
        panel = (FRONTEND / "components" / "model" / "PromotionGatePanel.tsx").read_text(encoding="utf-8")
        self.assertIn("失败原因", panel)
        self.assertIn("candidate", panel)
        self.assertIn("active", panel)
        self.assertIn("不会生成客户预测", panel)
        self.assertIn("sample 与 baseline 不允许晋级为 active", panel)


if __name__ == "__main__":
    unittest.main()
