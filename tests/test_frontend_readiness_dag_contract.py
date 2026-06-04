from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendReadinessDagContractTest(unittest.TestCase):
    def test_frontend_exposes_readiness_dag_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getReadinessDag", terminal)
        self.assertIn("refreshReadinessDag", terminal)
        self.assertIn("runSafeReadinessChecks", terminal)
        self.assertIn("/api/terminal/research/readiness-dag", terminal)
        self.assertIn("/api/terminal/research/refresh-readiness-dag", terminal)
        self.assertIn("/api/terminal/research/run-safe-readiness-checks", terminal)
        self.assertIn("ReadinessDagPayload", types)
        self.assertIn("critical_path", types)
        self.assertIn("forbidden_actions", types)
        self.assertIn("runnable_safe_checks", types)

    def test_model_research_page_renders_readiness_dag_card(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Readiness DAG", page)
        self.assertIn("current DAG status", page)
        self.assertIn("critical path", page)
        self.assertIn("blocked nodes", page)
        self.assertIn("Run safe checks", page)
        self.assertIn("forbidden actions", page)
        self.assertIn("next allowed action", page)


if __name__ == "__main__":
    unittest.main()
