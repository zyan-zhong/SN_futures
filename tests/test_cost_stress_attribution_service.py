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

from sn_futures.services.cost_stress_attribution_service import build_cost_stress_attribution


def _write_v10_report(output: Path) -> None:
    report_path = output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(
            {
                "status": "success",
                "candidate_version": "v10",
                "manual_approval_recommended": False,
                "institutional_cost_stress": {
                    "2x_cost": {"expectancy": -0.0002},
                    "3x_cost": {"expectancy": -0.0004},
                },
                "institutional_validation": {
                    "cost_stress": {
                        "2x_cost": {"expectancy": -0.0002},
                        "3x_cost": {"expectancy": -0.0004},
                    }
                },
                "training_invoked": True,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        ),
        encoding="utf-8",
    )


def _write_oof(output: Path, *, missing_time: bool = False, missing_regime: bool = False) -> None:
    oof_dir = output / "walk_forward" / "v10"
    oof_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        {
            "timestamp": ["2020-01-02", "2020-01-03", "2021-01-04", "2022-01-05"],
            "horizon": ["5d", "5d", "5d", "5d"],
            "regime_label": ["high_volatility", "high_volatility", "range", "low_volatility"],
            "predicted_direction": [1, -1, 1, -1],
            "realized_return": [0.0001, -0.0001, 0.00005, -0.00005],
            "confidence": [0.8, 0.7, 0.6, 0.6],
            "trade_edge": [0.002, 0.002, 0.001, 0.001],
            "cost_assumption": [0.0002, 0.0002, 0.0002, 0.0002],
            "label_start_time": ["2020-01-02", "2020-01-03", "2021-01-04", "2022-01-05"],
            "label_end_time": ["2020-01-07", "2020-01-08", "2021-01-09", "2022-01-10"],
        }
    )
    if missing_time:
        frame = frame.drop(columns=["timestamp", "label_start_time", "label_end_time"])
    if missing_regime:
        frame = frame.drop(columns=["regime_label"])
    frame.to_csv(oof_dir / "oof_trace_5d.csv", index=False)


class CostStressAttributionServiceTest(unittest.TestCase):
    def test_candidate_v10_negative_institutional_cost_stress_generates_failure_drivers_and_breakdowns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_v10_report(output)
            _write_oof(output)

            result = build_cost_stress_attribution("v10")

        self.assertEqual(result["candidate_version"], "v10")
        self.assertEqual(result["status"], "fail")
        self.assertIn("institutional_2x_cost_negative", result["failure_drivers"])
        self.assertIn("institutional_3x_cost_negative", result["failure_drivers"])
        self.assertGreater(len(result["by_horizon"]["rows"]), 0)
        self.assertGreater(len(result["by_regime"]["rows"]), 0)
        self.assertGreater(len(result["by_year"]["rows"]), 0)
        horizon_row = result["by_horizon"]["rows"][0]
        self.assertIn("gross_expectancy", horizon_row)
        self.assertIn("net_expectancy_2x", horizon_row)
        self.assertIn("cost_drag_3x", horizon_row)
        self.assertIn("signal_flip_rate", horizon_row)
        self.assertIn("avg_holding_period", horizon_row)
        self.assertIn("turnover_by_horizon", result["turnover_diagnostics"])
        self.assertIn("signal_flip_count", result["signal_flip_diagnostics"])
        self.assertIn("avg_holding_period", result["holding_period_diagnostics"])
        self.assertFalse(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_missing_time_field_marks_year_attribution_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_v10_report(output)
            _write_oof(output, missing_time=True)

            result = build_cost_stress_attribution("v10")

        self.assertEqual(result["by_year"]["status"], "missing")
        self.assertIn("year_time_column_missing", result["blocking_reasons"])
        self.assertFalse(result["passed"])

    def test_missing_regime_field_marks_regime_attribution_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_v10_report(output)
            _write_oof(output, missing_regime=True)

            result = build_cost_stress_attribution("v10")

        self.assertEqual(result["by_regime"]["status"], "missing")
        self.assertIn("regime_column_missing", result["blocking_reasons"])
        self.assertFalse(result["passed"])


if __name__ == "__main__":
    unittest.main()
