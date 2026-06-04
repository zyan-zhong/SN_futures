from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FeatureStoreV12FrontendContractTest(unittest.TestCase):
    def test_frontend_api_exposes_direct_v12_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getFeatureStoreV12", terminal)
        self.assertIn("buildFeatureStoreV12", terminal)
        self.assertIn("/api/terminal/feature-store/v12", terminal)
        self.assertIn("/api/terminal/feature-store/build-v12", terminal)
        self.assertIn("health_status", types)
        self.assertIn("audit_status", types)
        self.assertIn("managed_field_coverage", types)
        self.assertIn("point_in_time_join_ready", types)
        self.assertIn("training_dataset_v12_allowed", types)

    def test_factor_page_renders_v12_blocked_first_card(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Feature Store v12", page)
        self.assertIn("health status", page)
        self.assertIn("audit status", page)
        self.assertIn("managed field coverage", page)
        self.assertIn("timestamp coverage", page)
        self.assertIn("PIT join", page)
        self.assertIn("no-lookahead", page)
        self.assertIn("training dataset v12", page)


if __name__ == "__main__":
    unittest.main()
