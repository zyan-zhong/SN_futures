from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.active_absence_diagnostics_service import build_active_absence_diagnostics


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_active_absence_stability_fixture(root: Path) -> Path:
    output = root / "outputs"
    artifact = output / "model_registry" / "candidate_artifacts" / "v5" / "candidate_v5_1d.json"
    _write_json(
        artifact,
        {
            "model_id": "candidate_v5_1d",
            "horizon": "1d",
            "feature_importance": [
                {"feature": "roc_10", "importance": 0.5},
                {"feature": "atr_14", "importance": 0.4},
                {"feature": "basis_spread", "importance": 0.1},
            ],
        },
    )
    _write_json(
        output / "model_registry" / "candidate_v5_model_registry.json",
        {"models": [{"model_id": "candidate_v5_1d", "horizon": "1d", "artifact_path": str(artifact)}]},
    )
    _write_json(
        output / "model_registry" / "promotion_report_v5.json",
        {
            "candidate_version": "v5",
            "status": "failed",
            "promotion_gate_passed": False,
            "gate_results": [{"name": "PBO", "passed": False, "value": 0.7, "threshold": 0.2}],
        },
    )
    _write_json(
        output / "institutional_validation" / "institutional_validation_report_v5.json",
        {
            "candidate_version": "v5",
            "status": "failed",
            "passed": False,
            "feature_stability": {"feature_stability": []},
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "walk_forward" / "v5" / "wf_1d.json",
        {
            "candidate_version": "v5",
            "horizon": "1d",
            "folds": [
                {
                    "fold": 1,
                    "feature_importance": [
                        {"feature": "roc_10", "importance": 0.51},
                        {"feature": "atr_14", "importance": 0.39},
                        {"feature": "basis_spread", "importance": 0.10},
                    ],
                },
                {
                    "fold": 2,
                    "feature_importance": [
                        {"feature": "roc_10", "importance": 0.49},
                        {"feature": "atr_14", "importance": 0.41},
                        {"feature": "basis_spread", "importance": 0.10},
                    ],
                },
            ],
        },
    )
    return output


class ActiveAbsenceFeatureStabilityTest(unittest.TestCase):
    def test_active_absence_reads_feature_stability_evidence_instead_of_reporting_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_active_absence_stability_fixture(Path(tmp))

            report = build_active_absence_diagnostics()

            metric = report["blocking_metrics"]["feature_stability_score"]
            self.assertIsNotNone(metric["value"])
            self.assertGreaterEqual(metric["value"], 0.55)
            self.assertTrue(metric["passed"])
            self.assertNotIn("feature_stability", {item["category"] for item in report["root_causes"]})
            self.assertEqual(report["feature_stability_evidence"]["report_path"], str(output / "model_registry" / "feature_stability_report_v5.json"))
            self.assertIn("feature_stability", report["source_files"])
            self.assertFalse(report["active_updated"])
            self.assertFalse(report["customer_prediction_generated"])
            self.assertFalse((output / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()
