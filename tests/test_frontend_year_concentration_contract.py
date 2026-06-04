from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendYearConcentrationContractTest(unittest.TestCase):
    def test_frontend_exposes_year_concentration_api_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getYearConcentration", terminal)
        self.assertIn("refreshYearConcentration", terminal)
        self.assertIn("getCandidateV10Report", terminal)
        self.assertIn("/api/terminal/research/year-concentration", terminal)
        self.assertIn("/api/terminal/research/refresh-year-concentration", terminal)
        self.assertIn("/api/terminal/research/candidate-v10-report", terminal)
        self.assertIn("YearConcentrationEvidence", types)
        self.assertIn("max_year_pnl_share", types)
        self.assertIn("max_year_sample_share", types)
        self.assertIn("positive_year_count", types)
        self.assertIn("negative_year_count", types)
        self.assertIn("total_year_count", types)

    def test_model_research_page_renders_year_concentration_evidence_section(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Year Concentration Evidence", page)
        self.assertIn("Candidate v10 year evidence", page)
        self.assertIn("Candidate v12 year evidence", page)
        self.assertIn("max year pnl share", page)
        self.assertIn("max year sample share", page)
        self.assertIn("positive/negative/total years", page)
        self.assertIn("skipped reason", page)
        self.assertIn("blocking reasons", page)


if __name__ == "__main__":
    unittest.main()
