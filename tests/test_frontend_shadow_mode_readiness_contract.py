from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendShadowModeReadinessContractTest(unittest.TestCase):
    def test_frontend_exposes_shadow_mode_readiness_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getShadowModeReadiness", terminal)
        self.assertIn("refreshShadowModeReadiness", terminal)
        self.assertIn("/api/terminal/research/shadow-mode-readiness", terminal)
        self.assertIn("/api/terminal/research/refresh-shadow-mode-readiness", terminal)
        self.assertIn("ShadowModeReadinessPayload", types)
        self.assertIn("shadow_mode_allowed", types)
        self.assertIn("output_isolation_contract", types)
        self.assertIn("forbidden_outputs", types)

    def test_model_research_page_renders_shadow_mode_readiness_card(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Shadow Mode Readiness", page)
        self.assertIn("shadow_mode_allowed", page)
        self.assertIn("blocked gates", page)
        self.assertIn("output isolation contract", page)
        self.assertIn("Refresh shadow readiness", page)


if __name__ == "__main__":
    unittest.main()
