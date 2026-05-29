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


class ResearchEquityCurveTest(unittest.TestCase):
    def test_equity_curve_contains_cumulative_return_and_drawdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            trace_dir = Path(tmp) / "outputs" / "walk_forward" / "v3"
            trace_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                [
                    {
                        "candidate_version": "v3",
                        "horizon": "3d",
                        "fold_id": "1",
                        "timestamp": "2026-01-01",
                        "label_start_time": "2026-01-01",
                        "label_end_time": "2026-01-04",
                        "realized_direction": 1,
                        "realized_return": 0.01,
                        "predicted_direction": 1,
                        "confidence": 0.8,
                        "trade_edge": 0.009,
                        "cost_assumption": 0.0002,
                    },
                    {
                        "candidate_version": "v3",
                        "horizon": "3d",
                        "fold_id": "1",
                        "timestamp": "2026-01-02",
                        "label_start_time": "2026-01-02",
                        "label_end_time": "2026-01-05",
                        "realized_direction": -1,
                        "realized_return": -0.02,
                        "predicted_direction": 1,
                        "confidence": 0.75,
                        "trade_edge": 0.004,
                        "cost_assumption": 0.0002,
                    },
                ]
            ).to_csv(trace_dir / "oof_trace_3d.csv", index=False, encoding="utf-8")

            result = run_research_backtest(candidate_version="v3", horizons=("3d",))
            equity = pd.read_csv(result["horizons"]["3d"]["equity_curve_path"])
            drawdown = pd.read_csv(result["horizons"]["3d"]["drawdown_curve_path"])

        self.assertIn("equity", equity.columns)
        self.assertIn("strategy_return", equity.columns)
        self.assertIn("drawdown", drawdown.columns)
        self.assertLessEqual(float(drawdown["drawdown"].min()), 0.0)


if __name__ == "__main__":
    unittest.main()
