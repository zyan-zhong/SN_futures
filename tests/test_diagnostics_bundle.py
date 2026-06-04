from __future__ import annotations

import json
import os
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.full_system_report_service import build_full_system_txt_report


class DiagnosticsBundleContractTest(unittest.TestCase):
    def test_diagnostics_bundle_contains_expected_small_reports_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            (out / "diagnostics").mkdir(parents=True, exist_ok=True)
            (out / "feature_store" / "v5").mkdir(parents=True, exist_ok=True)
            (out / "training_datasets" / "v5").mkdir(parents=True, exist_ok=True)
            (out / "model_registry").mkdir(parents=True, exist_ok=True)
            (out / "research_backtests" / "v5").mkdir(parents=True, exist_ok=True)
            (out / "tasks").mkdir(parents=True, exist_ok=True)
            (out / "diagnostics" / "api_performance_report.json").write_text(json.dumps({"endpoints": []}), encoding="utf-8")
            (out / "feature_store" / "v5" / "feature_store_manifest.json").write_text(json.dumps({"version": "v5"}), encoding="utf-8")
            (out / "training_dataset_manifest_v5.json").write_text(json.dumps({"dataset_version": "v5"}), encoding="utf-8")
            (out / "model_registry" / "promotion_report_v5.json").write_text(json.dumps({"candidate_version": "v5"}), encoding="utf-8")
            (out / "research_backtests" / "v5" / "metrics_1d.json").write_text(json.dumps({"horizon": "1d"}), encoding="utf-8")
            (out / "tasks" / "task_history.json").write_text(json.dumps({"tasks": []}), encoding="utf-8")
            (Path(tmp) / "config").mkdir(parents=True, exist_ok=True)
            (Path(tmp) / "config" / "secrets.json").write_text('{"SN_NEWSAPI_KEY":"SHOULD_NOT_LEAK"}', encoding="utf-8")
            (out / "diagnostics" / "private_bundle_seed.json").write_text('{"secret":"SHOULD_NOT_LEAK"}', encoding="utf-8")

            result = build_full_system_txt_report()
            bundle_path = Path(result["diagnostics_bundle_path"])
            names: list[str]
            with zipfile.ZipFile(bundle_path) as zf:
                names = sorted(zf.namelist())
                combined = "\n".join(zf.read(name).decode("utf-8", errors="replace") for name in names)

            self.assertTrue(bundle_path.exists())
            self.assertIn("reports/full_system_report_latest.txt", names)
            self.assertIn("reports/full_system_report_latest.json", names)
            self.assertIn("diagnostics/api_performance_report.json", names)
            self.assertIn("diagnostics/data_consistency_report.json", names)
            self.assertIn("feature_store/feature_store_manifest.json", names)
            self.assertIn("training/training_dataset_manifest.json", names)
            self.assertIn("model/promotion_report.json", names)
            self.assertIn("backtest/metrics_1d.json", names)
            self.assertIn("tasks/task_history.json", names)
            self.assertIn("security/secret_scan_summary.json", names)
            self.assertFalse(any("secrets.json" in name for name in names))
            self.assertFalse(any("private_bundle_seed" in name for name in names))
            self.assertNotIn("SHOULD_NOT_LEAK", combined)


if __name__ == "__main__":
    unittest.main()
