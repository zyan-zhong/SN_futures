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


class CandidateV4ArtifactArchiveTest(unittest.TestCase):
    def test_candidate_v4_archive_copies_research_materials(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            (output / "feature_store" / "v4").mkdir(parents=True, exist_ok=True)
            (output / "feature_store" / "v4" / "feature_store_manifest.json").write_text(json.dumps({"version": "v4"}), encoding="utf-8")
            (output / "training_dataset_manifest_v4.json").write_text(json.dumps({"dataset_version": "v4"}), encoding="utf-8")
            (output / "model_registry").mkdir(parents=True, exist_ok=True)
            (output / "model_registry" / "candidate_v4_model_registry.json").write_text(json.dumps({"records": []}), encoding="utf-8")
            (output / "research_backtests" / "v4").mkdir(parents=True, exist_ok=True)
            (output / "research_backtests" / "v4" / "research_backtest_report.md").write_text("research backtest v4", encoding="utf-8")
            (output / "research_backtests" / "v4" / "equity_curve_1d.csv").write_text("x,y\n1,1\n", encoding="utf-8")
            (output / "research_backtests" / "v4" / "drawdown_curve_1d.csv").write_text("x,y\n1,0\n", encoding="utf-8")
            result = archive_research_run(candidate_version="v4", run_id="candidate_v4_test")
            archive_dir = Path(result["artifact_dir"])
            feature_store_exists = (archive_dir / "feature_store_manifest.json").exists()
            dataset_exists = (archive_dir / "training_dataset_manifest.json").exists()
            registry_exists = (archive_dir / "candidate_registry.json").exists()
            report_exists = (archive_dir / "research_backtest_report.md").exists()
            equity_exists = (archive_dir / "equity_curve_1d.csv").exists()
            drawdown_exists = (archive_dir / "drawdown_curve_1d.csv").exists()

        self.assertEqual(result["status"], "success")
        self.assertTrue(feature_store_exists)
        self.assertTrue(dataset_exists)
        self.assertTrue(registry_exists)
        self.assertTrue(report_exists)
        self.assertTrue(equity_exists)
        self.assertTrue(drawdown_exists)
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
