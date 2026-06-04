from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendTrainingDatasetV12ContractTest(unittest.TestCase):
    def test_frontend_api_exposes_v12_training_dataset_helpers(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getTrainingDatasetV12", terminal)
        self.assertIn("buildTrainingDatasetV12", terminal)
        self.assertIn("/api/terminal/training-dataset/v12", terminal)
        self.assertIn("/api/terminal/training-dataset/build-v12", terminal)
        self.assertIn("managed_interaction_feature_coverage", types)
        self.assertIn("managed_regime_counts", types)
        self.assertIn("sample_weight_summary", types)
        self.assertIn("candidate_v12_allowed", types)

    def test_training_data_page_renders_v12_status_card(self) -> None:
        page = (FRONTEND / "pages" / "TrainingDataPage.tsx").read_text(encoding="utf-8")

        self.assertIn('"v12"', page)
        self.assertIn("Feature Store v12 status", page)
        self.assertIn("managed field coverage", page)
        self.assertIn("managed interaction feature coverage", page)
        self.assertIn("managed regime distribution", page)
        self.assertIn("sample weight summary", page)
        self.assertIn("no-lookahead / PIT status", page)
        self.assertIn("blocked reasons", page)


if __name__ == "__main__":
    unittest.main()
