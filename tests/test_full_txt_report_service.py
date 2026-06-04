from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.full_system_report_service import build_full_system_txt_report, get_latest_full_system_txt_report


class FullSystemTxtReportServiceTest(unittest.TestCase):
    def test_full_txt_report_contains_required_sections_and_no_secret_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = build_full_system_txt_report()
            latest = get_latest_full_system_txt_report()
            text = Path(result["txt_path"]).read_text(encoding="utf-8")

        self.assertEqual(result["status"], "success")
        self.assertEqual(latest["status"], "success")
        for heading in [
            "1. Report Header",
            "2. Process And System",
            "3. Process Lifecycle",
            "4. API Health",
            "5. Data Sources",
            "6. Data Watermark",
            "7. Data Consistency",
            "8. Sample/Real Data Boundary",
            "9. Feature Coverage",
            "10. Training Data",
            "11. Models",
            "12. OOF / High Confidence",
            "13. Research Backtest",
            "14. Task Queue",
            "15. Frontend Status",
            "16. Security",
            "17. Known Issues",
            "18. Recommendations",
        ]:
            self.assertIn(heading, text)
        self.assertIn("shutdown_api", text)
        self.assertIn("port_release_validation", text)
        self.assertNotIn("apikey=", text.lower())
        self.assertNotIn("SN_NEWSAPI_KEY=", text)
        self.assertTrue(result["json_path"].endswith("full_system_report_latest.json"))


if __name__ == "__main__":
    unittest.main()
