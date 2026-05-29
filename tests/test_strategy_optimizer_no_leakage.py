from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.research_strategy_optimizer import optimize_research_strategy


class StrategyOptimizerNoLeakageTest(unittest.TestCase):
    def test_optimizer_does_not_use_validation_fold_to_select_threshold(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            trace_dir = Path(tmp) / "outputs" / "walk_forward" / "v3"
            trace_dir.mkdir(parents=True, exist_ok=True)
            rows = []
            for fold in range(1, 5):
                for idx in range(20):
                    rows.append(
                        {
                            "candidate_version": "v3",
                            "horizon": "1d",
                            "fold_id": str(fold),
                            "label_start_time": f"2026-01-{min(28, idx + 1):02d}",
                            "label_end_time": f"2026-01-{min(28, idx + 2):02d}",
                            "realized_direction": 1,
                            "realized_return": 0.002,
                            "predicted_direction": 1,
                            "confidence": 0.5 + idx * 0.02,
                            "trade_edge": 0.001 + idx * 0.0001,
                            "cost_assumption": 0.0002,
                            "regime_label": "RANGE",
                        }
                    )
            pd.DataFrame(rows).to_csv(trace_dir / "oof_trace_1d.csv", index=False, encoding="utf-8")

            result = optimize_research_strategy(candidate_version="v3", horizons=("1d",))
            trials = pd.read_csv(result["all_trials_path"])

        self.assertEqual(result["status"], "success")
        self.assertGreater(len(trials), 0)
        for _, row in trials.iterrows():
            validation_fold = str(row["validation_fold"])
            trained_on = str(row["trained_on_folds"]).split("|") if str(row["trained_on_folds"]) else []
            self.assertNotIn(validation_fold, trained_on)
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
