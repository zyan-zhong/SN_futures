from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.active_absence_diagnostics_service import build_active_absence_diagnostics
from active_absence_fixture import write_blocked_candidate_fixture


class ModelBlockerAttributionTest(unittest.TestCase):
    def test_blocking_metrics_quantify_validation_cost_stability_and_data_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            write_blocked_candidate_fixture(tmp)
            report = build_active_absence_diagnostics()

        metrics = report["blocking_metrics"]
        self.assertEqual(metrics["candidate_version"], "v5")
        self.assertGreater(metrics["pbo"]["value"], metrics["pbo"]["threshold"])
        self.assertLess(metrics["worst_fold_accuracy"]["value"], metrics["worst_fold_accuracy"]["threshold"])
        self.assertLess(metrics["cost_stress_2x_expectancy"]["value"], 0)
        self.assertLess(metrics["dsr"]["value"], metrics["dsr"]["threshold"])
        self.assertIn("basis", metrics["missing_factor_groups"])
        self.assertIn("lme_tin", metrics["missing_factor_groups"])
        self.assertEqual(metrics["data_source_status"]["tushare_provider_status"]["status"], "token_missing")
        self.assertEqual(metrics["data_source_status"]["managed_proxy_status"]["status"], "disabled")
        self.assertEqual(metrics["data_source_status"]["fx_macro_provider_status"]["status"], "rate_limited")
        self.assertEqual(metrics["data_source_status"]["news_provider_status"]["status"], "success")
        self.assertIn("data_source_status", report["source_files"])

    def test_root_cause_items_have_evidence_and_fix_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            write_blocked_candidate_fixture(tmp)
            report = build_active_absence_diagnostics()

        for item in report["root_causes"]:
            self.assertIn(item["severity"], {"P0", "P1", "P2"})
            self.assertTrue(item["evidence"])
            self.assertTrue(item["fix_plan"])


if __name__ == "__main__":
    unittest.main()
