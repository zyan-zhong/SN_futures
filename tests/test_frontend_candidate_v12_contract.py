from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendCandidateV12ContractTest(unittest.TestCase):
    def test_frontend_exposes_candidate_v12_helpers_and_types(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("runCandidateV12Research", terminal)
        self.assertIn("getCandidateV12Report", terminal)
        self.assertIn("/api/terminal/research/run-candidate-v12", terminal)
        self.assertIn("/api/terminal/research/candidate-v12-report", terminal)
        self.assertIn("CandidateV12ResearchPayload", types)
        self.assertIn("training_dataset_status", types)
        self.assertIn("feature_store_status", types)
        self.assertIn("readiness_checks", types)
        self.assertIn("year_concentration_evidence", types)
        self.assertIn("promotion_dry_run_result", types)

    def test_model_research_page_renders_candidate_v12_card(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")

        self.assertIn("candidate_v12 research gate", page)
        self.assertIn("Training Dataset v12 status", page)
        self.assertIn("Feature Store v12 status", page)
        self.assertIn("readiness checks", page)
        self.assertIn("training_invoked", page)
        self.assertIn("PBO", page)
        self.assertIn("Reality Check", page)
        self.assertIn("institutional 2x/3x cost", page)
        self.assertIn("year concentration", page)
        self.assertIn("v12 vs v10", page)
        self.assertIn("promotion dry-run", page)
        self.assertIn("manual_approval_recommended", page)
        self.assertIn("active/prediction status", page)


if __name__ == "__main__":
    unittest.main()
