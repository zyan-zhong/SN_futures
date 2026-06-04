from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedDataBackfillPlannerContractTest(unittest.TestCase):
    def test_frontend_api_exposes_backfill_planner_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ManagedDataBackfillPlannerPayload", types)
        self.assertIn("getManagedDataBackfillPlan", terminal)
        self.assertIn("refreshManagedDataBackfillPlan", terminal)
        self.assertIn("/api/terminal/managed-proxy/backfill-plan", terminal)
        self.assertIn("/api/terminal/managed-proxy/refresh-backfill-plan", terminal)

    def test_data_status_page_renders_backfill_planner_without_execution_inputs(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Real Managed Data Backfill Planner", page)
        self.assertIn("required date range", page.lower())
        self.assertIn("coverage budget", page.lower())
        self.assertIn("batch plan", page.lower())
        self.assertIn("abort conditions", page.lower())
        self.assertIn("planner does not execute backfill", page.lower())
        self.assertIn("production_cache_write_allowed", page)
        self.assertIn("feature_store_v12_allowed", page)
        self.assertIn("rows_fetched", page)
        self.assertNotIn('type="password"', page)
        self.assertNotIn("raw token input", page.lower())
        self.assertNotIn("custom output path", page.lower())


if __name__ == "__main__":
    unittest.main()
