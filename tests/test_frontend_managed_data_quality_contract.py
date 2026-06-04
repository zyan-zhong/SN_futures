from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedDataQualityContractTest(unittest.TestCase):
    def test_frontend_api_exposes_managed_data_quality_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getManagedDataQuality", terminal)
        self.assertIn("refreshManagedDataQuality", terminal)
        self.assertIn("/api/terminal/managed-proxy/data-quality", terminal)
        self.assertIn("/api/terminal/managed-proxy/refresh-data-quality", terminal)
        self.assertIn("ManagedDataQualityPayload", types)
        self.assertIn("quality_score", types)

    def test_data_status_page_renders_quality_scorecard(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Data Quality Scorecard", page)
        self.assertIn("quality score", page)
        self.assertIn("missing rates", page)
        self.assertIn("null_rate_by_field", page)
        self.assertIn("duplicate count", page)
        self.assertIn("invalid values", page)
        self.assertIn("outliers", page)
        self.assertIn("contract switch anomalies", page)
        self.assertIn("gate result", page)


if __name__ == "__main__":
    unittest.main()
