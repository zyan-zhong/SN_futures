from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.multi_objective_research_optimizer import optimize_multi_objective_research_strategy


def _write_oof(root: str, version: str = "v5", horizon: str = "1d") -> None:
    trace_dir = Path(root) / "outputs" / "walk_forward" / version
    trace_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for fold in range(1, 5):
        for idx in range(30):
            direction = 1 if idx % 2 else -1
            rows.append(
                {
                    "candidate_version": version,
                    "dataset_version": version,
                    "horizon": horizon,
                    "fold_id": str(fold),
                    "label_start_time": f"2026-01-{min(idx + 1, 28):02d}",
                    "label_end_time": f"2026-01-{min(idx + 2, 28):02d}",
                    "realized_direction": direction,
                    "realized_return": 0.004 * direction,
                    "predicted_direction": direction,
                    "confidence": 0.62 + idx * 0.002,
                    "trade_edge": 0.001 + idx * 0.0001,
                    "cost_assumption": 0.0002,
                    "regime_label": "RANGE",
                }
            )
    pd.DataFrame(rows).to_csv(trace_dir / f"oof_trace_{horizon}.csv", index=False, encoding="utf-8")


class MultiObjectiveOptimizerTest(unittest.TestCase):
    def test_optimizer_writes_objectives_constraints_and_does_not_update_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_oof(tmp)
            result = optimize_multi_objective_research_strategy(candidate_version="v5", horizons=("1d",))
            report_path = Path(result["report_path"])
            trials_path = Path(result["all_trials_path"])
            output = Path(tmp) / "outputs"
            report_exists = report_path.exists()
            trials_exists = trials_path.exists()
            active_exists = (output / "model_registry" / "active_model.json").exists()
            prediction_exists = (output / "sn_live_predictions.json").exists()

        self.assertEqual(result["candidate_version"], "v5")
        self.assertEqual(result["status"], "success")
        self.assertTrue(report_exists)
        self.assertTrue(trials_exists)
        self.assertIn("maximize", result["objectives"])
        self.assertIn("minimize", result["objectives"])
        self.assertIn("2x_cost_stress_non_negative", result["constraints"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])
        self.assertFalse(active_exists)
        self.assertFalse(prediction_exists)


if __name__ == "__main__":
    unittest.main()
