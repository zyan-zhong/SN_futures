from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.research_backtest_service import run_research_backtest


class ResearchBacktestV5Test(unittest.TestCase):
    def test_v5_research_backtest_writes_curves_trades_metrics_from_oof_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            trace_dir = Path(tmp) / "outputs" / "walk_forward" / "v5"
            trace_dir.mkdir(parents=True, exist_ok=True)
            rows = []
            for idx in range(45):
                direction = 1 if idx % 3 else -1
                rows.append(
                    {
                        "candidate_version": "v5",
                        "dataset_version": "v5",
                        "horizon": "1d",
                        "fold_id": str(1 + idx // 15),
                        "timestamp": f"2026-03-{min(idx % 28 + 1, 28):02d}",
                        "label_start_time": f"2026-03-{min(idx % 28 + 1, 28):02d}",
                        "label_end_time": f"2026-03-{min(idx % 28 + 2, 28):02d}",
                        "realized_direction": direction,
                        "realized_return": 0.003 * direction,
                        "predicted_direction": direction,
                        "confidence": 0.72,
                        "trade_edge": 0.002,
                        "selected_signal": "research_signal",
                        "cost_assumption": 0.0002,
                        "regime_label": "RANGE",
                    }
                )
            pd.DataFrame(rows).to_csv(trace_dir / "oof_trace_1d.csv", index=False, encoding="utf-8")
            result = run_research_backtest(candidate_version="v5", horizons=("1d",))
            horizon = result["horizons"]["1d"]
            output = Path(tmp) / "outputs"
            equity_exists = Path(horizon["equity_curve_path"]).exists()
            drawdown_exists = Path(horizon["drawdown_curve_path"]).exists()
            trades_exists = Path(horizon["trades_path"]).exists()
            metrics_exists = Path(horizon["metrics_path"]).exists()
            active_exists = (output / "model_registry" / "active_model.json").exists()
            prediction_exists = (output / "sn_live_predictions.json").exists()

        self.assertEqual(result["status"], "success")
        self.assertTrue(equity_exists)
        self.assertTrue(drawdown_exists)
        self.assertTrue(trades_exists)
        self.assertTrue(metrics_exists)
        self.assertEqual(horizon["metrics"]["signal_source"], "oof_trace_only")
        self.assertIn("2x_cost", horizon["metrics"]["cost_stress"])
        self.assertIn("3x_cost", horizon["metrics"]["cost_stress"])
        self.assertFalse(active_exists)
        self.assertFalse(prediction_exists)


if __name__ == "__main__":
    unittest.main()
