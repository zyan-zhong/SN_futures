from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendFeatureStoreV12BuildPlanTest(unittest.TestCase):
    def test_frontend_api_exposes_v12_build_plan_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("FeatureStoreV12BuildPlanPayload", types)
        self.assertIn("getFeatureStoreV12BuildPlan", terminal)
        self.assertIn("refreshFeatureStoreV12BuildPlan", terminal)
        self.assertIn("/api/terminal/feature-store/v12-build-plan", terminal)
        self.assertIn("/api/terminal/feature-store/refresh-v12-build-plan", terminal)

    def test_factor_page_renders_v12_build_plan_card_without_real_build_controls(self) -> None:
        factor_page = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")

        self.assertIn("v12 Build Dry-Run Plan", factor_page)
        self.assertIn("feature_store_v12_build_executed", factor_page)
        self.assertIn("expected_feature_store_path", factor_page)
        self.assertIn("expected_manifest_path", factor_page)
        self.assertIn("resource_budget", factor_page)
        self.assertIn("forbidden_side_effects", factor_page)
        self.assertNotIn("raw token input", factor_page.lower())


if __name__ == "__main__":
    unittest.main()
