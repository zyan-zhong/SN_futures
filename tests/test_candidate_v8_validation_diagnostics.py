from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from candidate_v8_diagnostics_fixtures import write_v8_diagnostics_fixture
from sn_futures.services.candidate_v8_diagnostics_service import build_candidate_v8_validation_diagnostics


class CandidateV8ValidationDiagnosticsTest(unittest.TestCase):
    def test_reads_failed_institutional_validation_and_writes_reports_without_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = write_v8_diagnostics_fixture(Path(tmp))
            result = build_candidate_v8_validation_diagnostics()

            self.assertEqual(result["candidate_version"], "v8")
            self.assertEqual(result["institutional_validation_status"], "failed")
            self.assertFalse(result["validation_passed"])
            self.assertIn("PBO", [item["name"] for item in result["failed_checks"]])
            self.assertIn("Reality Check", [item["name"] for item in result["failed_checks"]])
            self.assertTrue(Path(result["json_path"]).exists())
            self.assertTrue(Path(result["markdown_path"]).exists())
            self.assertFalse((out / "model_registry" / "active_model.json").exists())
            self.assertFalse(result["active_updated"])
            self.assertFalse(result["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
