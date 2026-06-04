from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendFeatureStoreV12InputContractTest(unittest.TestCase):
    def test_frontend_api_exposes_v12_input_contract_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("FeatureStoreV12InputContractPayload", types)
        self.assertIn("getFeatureStoreV12InputContract", terminal)
        self.assertIn("refreshFeatureStoreV12InputContract", terminal)
        self.assertIn("/api/terminal/feature-store/v12-input-contract", terminal)
        self.assertIn("/api/terminal/feature-store/refresh-v12-input-contract", terminal)

    def test_data_and_factor_pages_render_v12_input_contract_cards(self) -> None:
        data_page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")
        factor_page = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")

        for page in (data_page, factor_page):
            self.assertIn("v12 Input Contract", page)
            self.assertIn("input_contract_ready", page)
            self.assertIn("missing_required_fields", page)
            self.assertIn("missing_timestamp_fields", page)
            self.assertIn("coverage diff", page.lower())
            self.assertIn("feature_store_v12_build_allowed", page)
            self.assertNotIn('type="password"', page)
            self.assertNotIn("raw token input", page.lower())


if __name__ == "__main__":
    unittest.main()
