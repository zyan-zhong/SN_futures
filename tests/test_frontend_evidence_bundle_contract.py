from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendEvidenceBundleContractTest(unittest.TestCase):
    def test_frontend_exposes_evidence_bundle_api_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getEvidenceBundle", terminal)
        self.assertIn("refreshEvidenceBundle", terminal)
        self.assertIn("/api/terminal/research/evidence-bundle", terminal)
        self.assertIn("/api/terminal/research/refresh-evidence-bundle", terminal)
        self.assertIn("EvidenceBundlePayload", types)
        self.assertIn("reproducibility_checklist", types)
        self.assertIn("no_active_confirmation", types)
        self.assertIn("no_prediction_confirmation", types)

    def test_model_research_page_renders_evidence_bundle_card(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Evidence Bundle", page)
        self.assertIn("bundle status", page)
        self.assertIn("evidence file count", page)
        self.assertIn("missing/incomplete reports", page)
        self.assertIn("Refresh evidence bundle", page)
        self.assertIn("next allowed action", page)


if __name__ == "__main__":
    unittest.main()
