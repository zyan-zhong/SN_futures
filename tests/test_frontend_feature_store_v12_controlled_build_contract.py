from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendFeatureStoreV12ControlledBuildContractTest(unittest.TestCase):
    def test_frontend_api_exposes_controlled_build_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("FeatureStoreV12ControlledBuildPayload", types)
        self.assertIn("getFeatureStoreV12ControlledBuild", terminal)
        self.assertIn("runFeatureStoreV12ControlledBuild", terminal)
        self.assertIn("/api/terminal/feature-store/v12-controlled-build", terminal)
        self.assertIn("/api/terminal/feature-store/run-v12-controlled-build", terminal)

    def test_factor_page_renders_controlled_executor_card_without_downstream_controls(self) -> None:
        factor_page = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")

        self.assertIn("v12 Controlled Build Executor", factor_page)
        self.assertIn("build_executed", factor_page)
        self.assertIn("feature_store_v12_path", factor_page)
        self.assertIn("artifact_boundary_checks", factor_page)
        self.assertIn("does not trigger TD v12 or candidate", factor_page)
        self.assertNotIn("force controlled build", factor_page.lower())
        self.assertNotIn("raw token input", factor_page.lower())


if __name__ == "__main__":
    unittest.main()
