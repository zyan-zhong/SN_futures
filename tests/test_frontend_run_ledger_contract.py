from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendRunLedgerContractTest(unittest.TestCase):
    def test_frontend_exposes_run_ledger_api_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getRunLedger", terminal)
        self.assertIn("refreshRunLedger", terminal)
        self.assertIn("/api/terminal/research/run-ledger", terminal)
        self.assertIn("/api/terminal/research/refresh-run-ledger", terminal)
        self.assertIn("ResearchRunLedgerPayload", types)
        self.assertIn("violation_count", types)
        self.assertIn("safe_check_count", types)
        self.assertIn("heavy_task_count", types)

    def test_research_page_renders_run_ledger_card(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Run Ledger", page)
        self.assertIn("latest runs", page)
        self.assertIn("violation count", page)
        self.assertIn("safe checks vs heavy tasks", page)
        self.assertIn("forbidden side effects", page)
        self.assertIn("Refresh run ledger", page)


if __name__ == "__main__":
    unittest.main()
