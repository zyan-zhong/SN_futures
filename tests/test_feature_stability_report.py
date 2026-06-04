from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.full_system_report_service import build_full_system_txt_report
from sn_futures.services.institutional_validation_service import get_institutional_validation_report

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_stability_sources(root: Path) -> Path:
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
        {
            "models": [
                {
                    "model_id": "candidate_v5_1d",
                    "horizon": "1d",
                    "artifact_path": str(artifact),
                }
            ]
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
                        {"feature": "roc_10", "importance": 0.52},
                        {"feature": "atr_14", "importance": 0.38},
                        {"feature": "basis_spread", "importance": 0.10},
                    ],
                },
                {
                    "fold": 2,
                    "feature_importance": [
                        {"feature": "roc_10", "importance": 0.51},
                        {"feature": "atr_14", "importance": 0.39},
                        {"feature": "basis_spread", "importance": 0.10},
                    ],
                },
            ],
        },
    )
    _write_json(
        output / "institutional_validation" / "institutional_validation_report_v5.json",
        {
            "candidate_version": "v5",
            "status": "failed",
            "passed": False,
            "feature_stability": {"feature_stability": [], "unstable_feature_blacklist": []},
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    return output


class FeatureStabilityReportIntegrationTest(unittest.TestCase):
    def test_institutional_report_is_enriched_with_feature_stability_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_stability_sources(Path(tmp))

            report = get_institutional_validation_report(candidate_version="v5")

            stability = report["feature_stability"]
            self.assertGreaterEqual(stability["stability_score"], 0.55)
            self.assertTrue(stability["passed"])
            self.assertIn("roc_10", stability["stable_features"])
            self.assertEqual(stability["evidence_report_path"], str(output / "model_registry" / "feature_stability_report_v5.json"))
            persisted = json.loads((output / "institutional_validation" / "institutional_validation_report_v5.json").read_text(encoding="utf-8"))
            self.assertEqual(persisted["feature_stability"]["stability_score"], stability["stability_score"])

    def test_full_system_report_includes_feature_stability_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_stability_sources(Path(tmp))

            result = build_full_system_txt_report()
            latest = json.loads((output / "reports" / "full_system_report_latest.json").read_text(encoding="utf-8"))

            self.assertEqual(result["status"], "success")
            self.assertIn("feature_stability", latest)
            self.assertGreaterEqual(latest["feature_stability"]["stability_score"], 0.55)
            self.assertIn("feature_stability_score", (output / "reports" / "full_system_report_latest.txt").read_text(encoding="utf-8"))

    def test_model_research_page_displays_feature_stability_evidence(self) -> None:
        page = (FRONTEND / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("feature_stability_evidence", types)
        self.assertIn("Feature stability score", page)
        self.assertIn("unstable features", page)
        self.assertIn("recommendation", page)


if __name__ == "__main__":
    unittest.main()
