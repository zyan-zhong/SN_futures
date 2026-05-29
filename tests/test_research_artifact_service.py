from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.research_artifact_service import archive_research_run


class ResearchArtifactServiceTest(unittest.TestCase):
    def test_artifact_archive_copies_available_research_materials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            (output / "feature_store" / "v3").mkdir(parents=True, exist_ok=True)
            (output / "feature_store" / "v3" / "feature_store_manifest.json").write_text(json.dumps({"version": "v3"}), encoding="utf-8")
            (output / "training_dataset_manifest_v3.json").write_text(json.dumps({"dataset_version": "v3"}), encoding="utf-8")
            (output / "model_registry").mkdir(parents=True, exist_ok=True)
            (output / "model_registry" / "candidate_v3_model_registry.json").write_text(json.dumps({"records": []}), encoding="utf-8")
            (output / "research_backtests" / "v3").mkdir(parents=True, exist_ok=True)
            (output / "research_backtests" / "v3" / "research_backtest_report.md").write_text("research backtest", encoding="utf-8")

            result = archive_research_run(candidate_version="v3", run_id="test_run")
            archive_dir = Path(result["artifact_dir"])
            config_exists = (archive_dir / "config.json").exists()
            feature_store_exists = (archive_dir / "feature_store_manifest.json").exists()
            dataset_exists = (archive_dir / "training_dataset_manifest.json").exists()
            registry_exists = (archive_dir / "candidate_registry.json").exists()
            report_exists = (archive_dir / "research_backtest_report.md").exists()

        self.assertEqual(result["status"], "success")
        self.assertTrue(config_exists)
        self.assertTrue(feature_store_exists)
        self.assertTrue(dataset_exists)
        self.assertTrue(registry_exists)
        self.assertTrue(report_exists)
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
