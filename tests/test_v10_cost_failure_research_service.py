from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import sys

sys.path.insert(0, "src")

from sn_futures.services.v10_cost_failure_research_service import build_cost_failure_research_report


def _write_candidate_report(output: Path) -> Path:
    report_path = output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "status": "success",
        "candidate_version": "v10",
        "gate_passed": False,
        "manual_approval_recommended": False,
        "institutional_cost_stress": {
            "2x_cost": {"expectancy": -0.0002},
            "3x_cost": {"expectancy": -0.0004},
        },
        "v10_gate_checks": {
            "cost_pressure_positive": False,
            "two_x_cost_expectancy": -0.0002,
            "three_x_cost_expectancy": -0.0004,
        },
        "training_invoked": True,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report_path


def _write_oof(output: Path) -> None:
    oof_dir = output / "walk_forward" / "v10"
    oof_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "timestamp": ["2020-01-02", "2022-01-03", "2022-01-04", "2023-01-05"],
            "horizon": ["1d", "1d", "5d", "20d"],
            "regime_label": ["range", "high_volatility", "high_volatility", "low_volatility"],
            "predicted_direction": [1, 1, -1, 1],
            "realized_return": [0.001, -0.0001, 0.004, 0.006],
            "confidence": [0.55, 0.51, 0.84, 0.9],
            "trade_edge": [0.0001, 0.0001, 0.003, 0.004],
            "cost_assumption": [0.0002, 0.0002, 0.0002, 0.0002],
            "label_start_time": ["2020-01-02", "2022-01-03", "2022-01-04", "2023-01-05"],
            "label_end_time": ["2020-01-03", "2022-01-04", "2022-01-09", "2023-01-25"],
        }
    )
    frame.to_csv(oof_dir / "oof_trace_1d.csv", index=False)


class V10CostFailureResearchServiceTest(unittest.TestCase):
    def test_missing_oof_skips_counterfactuals_without_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_candidate_report(output)

            report = build_cost_failure_research_report()

        self.assertEqual(report["status"], "skipped")
        self.assertIn("oof_trace_missing", report["blocking_reasons"])
        self.assertEqual(report["no_train_counterfactuals"], [])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_existing_oof_generates_research_only_hypotheses_and_counterfactuals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_candidate_report(output)
            _write_oof(output)

            report = build_cost_failure_research_report()

        titles = {item["id"] for item in report["hypotheses"]}
        self.assertEqual(report["status"], "ready")
        self.assertIn("filter_1d_horizon", titles)
        self.assertIn("reduce_high_volatility_exposure", titles)
        self.assertIn("increase_turnover_penalty", titles)
        self.assertIn("limit_signal_flip", titles)
        self.assertIn("minimum_holding_period", titles)
        self.assertIn("stress_2022_filter", titles)
        self.assertIn("cost_aware_thresholding", titles)
        self.assertGreater(len(report["no_train_counterfactuals"]), 0)
        self.assertTrue(all(item["research_only"] for item in report["no_train_counterfactuals"]))
        self.assertFalse(report["manual_approval_recommended"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_report_does_not_mutate_candidate_v10_gate_or_write_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            candidate_path = _write_candidate_report(output)
            _write_oof(output)
            before = json.loads(candidate_path.read_text(encoding="utf-8"))

            report = build_cost_failure_research_report()
            after = json.loads(candidate_path.read_text(encoding="utf-8"))

        self.assertEqual(before["gate_passed"], after["gate_passed"])
        self.assertEqual(before["manual_approval_recommended"], after["manual_approval_recommended"])
        self.assertEqual(before["v10_gate_checks"], after["v10_gate_checks"])
        self.assertFalse(report["manual_approval_recommended"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "customer_predictions").exists())


if __name__ == "__main__":
    unittest.main()
