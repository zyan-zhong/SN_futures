from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendEvidenceFreshnessContractTest(unittest.TestCase):
    def test_frontend_exposes_evidence_freshness_api_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getEvidenceFreshness", terminal)
        self.assertIn("refreshEvidenceFreshness", terminal)
        self.assertIn("/api/terminal/research/evidence-freshness", terminal)
        self.assertIn("/api/terminal/research/refresh-evidence-freshness", terminal)
        self.assertIn("EvidenceFreshnessPayload", types)
        self.assertIn("stale_reports", types)
        self.assertIn("missing_timestamps", types)
        self.assertIn("timestamp_inversions", types)

    def test_model_research_page_renders_evidence_freshness_card(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Evidence Freshness", page)
        self.assertIn("freshness status", page)
        self.assertIn("stale reports", page)
        self.assertIn("missing timestamps", page)
        self.assertIn("timestamp inversions", page)
        self.assertIn("Refresh freshness", page)


if __name__ == "__main__":
    unittest.main()
