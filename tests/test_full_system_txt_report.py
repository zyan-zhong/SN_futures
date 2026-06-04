from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.full_system_report_service import build_full_system_txt_report


class FullSystemTxtReportContractTest(unittest.TestCase):
    def test_full_system_txt_report_has_problem_diagnosis_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = build_full_system_txt_report()
            text = Path(result["latest_txt_path"]).read_text(encoding="utf-8")
            json_path = Path(result["json_path"])

        self.assertEqual(result["status"], "success")
        self.assertTrue(json_path.name.endswith("latest.json"))
        for heading in [
            "System Version",
            "Process Status",
            "API Performance Table",
            "Data Source Status",
            "Data Watermark",
            "Sample/Real Data Boundary",
            "Factor Coverage",
            "Feature Store",
            "Training Data",
            "Candidate/Active Status",
            "OOF",
            "Backtest Equity Summary",
            "Task Queue",
            "Frontend Page Status",
            "Secret Scan Result",
            "Error Log Summary",
            "P0/P1/P2 Recommendations",
        ]:
            self.assertIn(heading, text)
        self.assertIn("diagnostics_bundle.zip", str(result.get("diagnostics_bundle_path", "")))


if __name__ == "__main__":
    unittest.main()
