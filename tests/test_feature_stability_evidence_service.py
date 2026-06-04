from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.feature_stability_evidence_service import build_feature_stability_evidence


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_candidate_v5_feature_stability_fixture(root: Path) -> Path:
    output = root / "outputs"
    artifact_dir = output / "model_registry" / "candidate_artifacts" / "v5"
    artifact_path = artifact_dir / "candidate_v5_1d.json"
    _write_json(
        artifact_path,
        {
            "model_id": "candidate_v5_1d",
            "candidate_version": "v5",
            "horizon": "1d",
            "feature_importance": [
                {"feature": "roc_10", "importance": 0.40},
                {"feature": "atr_14", "importance": 0.35},
                {"feature": "macro_spike", "importance": 0.25},
            ],
        },
    )
    _write_json(
        output / "model_registry" / "candidate_v5_model_registry.json",
        {
            "updated_at": "2099-01-01T00:00:00",
            "models": [
                {
                    "model_id": "candidate_v5_1d",
                    "horizon": "1d",
                    "artifact_path": str(artifact_path),
                    "feature_columns": ["roc_10", "atr_14", "macro_spike"],
                }
            ],
        },
    )
    _write_json(
        output / "walk_forward" / "v5" / "wf_1d.json",
        {
            "candidate_version": "v5",
            "horizon": "1d",
            "status": "success",
            "folds": [
                {
                    "fold": 1,
                    "feature_importance": [
                        {"feature": "roc_10", "importance": 0.48},
                        {"feature": "atr_14", "importance": 0.42},
                        {"feature": "macro_spike", "importance": 0.10},
                    ],
                },
                {
                    "fold": 2,
                    "feature_importance": [
                        {"feature": "roc_10", "importance": 0.46},
                        {"feature": "atr_14", "importance": 0.40},
                        {"feature": "macro_spike", "importance": 0.14},
                    ],
                },
                {
                    "fold": 3,
                    "feature_importance": [
                        {"feature": "roc_10", "importance": 0.45},
                        {"feature": "atr_14", "importance": 0.43},
                        {"feature": "macro_spike", "importance": 0.12},
                    ],
                },
            ],
        },
    )
    return output


class FeatureStabilityEvidenceServiceTest(unittest.TestCase):
    def test_builds_feature_stability_evidence_from_candidate_v5_folds_without_model_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_candidate_v5_feature_stability_fixture(Path(tmp))

            report = build_feature_stability_evidence(candidate_version="v5")

            self.assertEqual(report["candidate_version"], "v5")
            self.assertEqual(report["fold_count"], 3)
            self.assertGreaterEqual(report["stability_score"], 0.55)
            self.assertTrue(report["passed"])
            self.assertIn("roc_10", report["stable_features"])
            self.assertIn("atr_14", report["stable_features"])
            self.assertEqual(report["permutation_importance_status"], "unavailable")
            self.assertFalse(report["active_updated"])
            self.assertFalse(report["customer_prediction_generated"])
            self.assertTrue((output / "model_registry" / "feature_stability_report_v5.json").exists())
            self.assertFalse((output / "model_registry" / "active_model.json").exists())
            self.assertFalse((output / "customer_predictions").exists())


if __name__ == "__main__":
    unittest.main()
