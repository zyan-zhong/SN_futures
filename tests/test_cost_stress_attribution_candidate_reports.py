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

from sn_futures.services.cost_stress_attribution_service import refresh_cost_stress_attribution


class CostStressAttributionCandidateReportTest(unittest.TestCase):
    def test_refresh_writes_v10_and_skipped_v12_without_training_or_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            v10_path = output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json"
            v12_path = output / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json"
            v10_path.parent.mkdir(parents=True, exist_ok=True)
            v12_path.parent.mkdir(parents=True, exist_ok=True)
            v10_path.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "candidate_version": "v10",
                        "manual_approval_recommended": False,
                        "institutional_cost_stress": {
                            "2x_cost": {"expectancy": -0.0002},
                            "3x_cost": {"expectancy": -0.0004},
                        },
                        "training_invoked": True,
                        "active_updated": False,
                        "customer_prediction_generated": False,
                    }
                ),
                encoding="utf-8",
            )
            v12_path.write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "candidate_version": "v12",
                        "blocking_reasons": ["training_dataset_v12_blocked"],
                        "manual_approval_recommended": False,
                        "training_invoked": False,
                        "active_updated": False,
                        "customer_prediction_generated": False,
                    }
                ),
                encoding="utf-8",
            )
            oof_dir = output / "walk_forward" / "v10"
            oof_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                {
                    "timestamp": ["2020-01-01", "2021-01-01", "2022-01-01"],
                    "horizon": ["5d", "5d", "5d"],
                    "regime_label": ["high_volatility", "range", "low_volatility"],
                    "predicted_direction": [1, 1, 1],
                    "realized_return": [0.0001, 0.0001, 0.0001],
                    "confidence": [0.8, 0.8, 0.8],
                    "trade_edge": [0.001, 0.001, 0.001],
                    "cost_assumption": [0.0002, 0.0002, 0.0002],
                    "label_start_time": ["2020-01-01", "2021-01-01", "2022-01-01"],
                    "label_end_time": ["2020-01-06", "2021-01-06", "2022-01-06"],
                }
            ).to_csv(oof_dir / "oof_trace_5d.csv", index=False)

            summary = refresh_cost_stress_attribution()
            v10 = json.loads(v10_path.read_text(encoding="utf-8"))
            v12 = json.loads(v12_path.read_text(encoding="utf-8"))

        self.assertTrue(summary["reports_rewritten"])
        self.assertEqual(v10["cost_stress_attribution"]["status"], "fail")
        self.assertIn("institutional_2x_cost_negative", v10["cost_stress_attribution"]["failure_drivers"])
        self.assertFalse(v10["manual_approval_recommended"])
        self.assertEqual(v12["cost_stress_attribution"]["status"], "skipped")
        self.assertIn("candidate_v12_blocked", v12["cost_stress_attribution"]["blocking_reasons"])
        self.assertIn("training_dataset_v12_blocked", v12["cost_stress_attribution"]["blocking_reasons"])
        self.assertIn("oof_trace_missing", v12["cost_stress_attribution"]["blocking_reasons"])
        self.assertIn("training_not_invoked", v12["cost_stress_attribution"]["blocking_reasons"])
        self.assertFalse(summary["training_invoked"])
        self.assertFalse(summary["active_updated"])
        self.assertFalse(summary["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
