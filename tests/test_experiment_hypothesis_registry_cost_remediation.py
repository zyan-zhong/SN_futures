from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.experiment_hypothesis_registry_service import (
    build_hypothesis_templates_from_v10_cost_remediation,
)


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class ExperimentHypothesisRegistryCostRemediationTest(unittest.TestCase):
    def test_each_recommended_cost_remediation_experiment_gets_hypothesis_template(self) -> None:
        tmp = _workspace_tmp("hypothesis-cost-template")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            report_path = Path(tmp) / "outputs" / "model_research" / "candidate_v10" / "v10_cost_failure_research_report.json"
            _write_json(
                report_path,
                {
                    "status": "ready",
                    "recommended_next_experiment": "cost_aware_thresholding",
                    "ranked_hypotheses": [
                        {
                            "id": "cost_aware_thresholding",
                            "title": "Cost-aware thresholding",
                            "affected_horizon": "1d",
                            "affected_regime": "high_volatility",
                            "affected_year": 2022,
                            "expected_tradeoff": "fewer trades",
                            "risk_of_overfitting": "low",
                        },
                        {
                            "id": "increase_turnover_penalty",
                            "title": "Increase turnover penalty",
                            "affected_horizon": "1d",
                            "affected_regime": "range",
                            "affected_year": 2022,
                            "expected_tradeoff": "lower turnover",
                            "risk_of_overfitting": "medium",
                        },
                    ],
                    "training_invoked": False,
                    "active_updated": False,
                    "customer_prediction_generated": False,
                },
            )

            templates = build_hypothesis_templates_from_v10_cost_remediation()

        self.assertEqual(templates["status"], "ready")
        self.assertEqual(len(templates["templates"]), 2)
        self.assertEqual(templates["templates"][0]["linked_blocker"], "cost_attribution:institutional_cost_negative")
        self.assertFalse(templates["training_invoked"])
        self.assertFalse(templates["active_updated"])
        self.assertFalse(templates["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
