from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendModelRegistrySafetyContractTest(unittest.TestCase):
    def test_frontend_exposes_model_registry_safety_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getModelRegistrySafety", terminal)
        self.assertIn("refreshModelRegistrySafety", terminal)
        self.assertIn("/api/terminal/research/model-registry-safety", terminal)
        self.assertIn("/api/terminal/research/refresh-model-registry-safety", terminal)
        self.assertIn("ModelRegistrySafetyPayload", types)
        self.assertIn("active_write_allowed", types)
        self.assertIn("rollback_target_available", types)
        self.assertIn("unapproved_active_detected", types)

    def test_model_research_page_renders_registry_safety_card(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Registry Safety / Rollback", page)
        self.assertIn("active_write_allowed", page)
        self.assertIn("rollback_target_available", page)
        self.assertIn("unapproved_active_detected", page)
        self.assertIn("Refresh registry safety", page)


if __name__ == "__main__":
    unittest.main()
