from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from smoke_train_pipeline import run_smoke_pipeline
from sn_futures.backtest_core import BacktestConfig, run_futures_backtest


class PipelineIntegrationTests(unittest.TestCase):
    def test_smoke_pipeline_runs_on_mock_data(self) -> None:
        result = run_smoke_pipeline()
        self.assertGreater(result["feature_count"], 5)
        self.assertGreater(result["metadata_count"], 10)
        self.assertEqual(result["prediction_count"], 24)
        self.assertIn("directional_accuracy", result["model_metrics"])
        self.assertIn("net_profit_after_cost", result["backtest_metrics"])

    def test_observation_signal_produces_no_trade(self) -> None:
        idx = pd.date_range("2026-01-01", periods=4, freq="D")
        bars = pd.DataFrame(
            {
                "open": [100, 101, 102, 103],
                "high": [101, 102, 103, 104],
                "low": [99, 100, 101, 102],
                "close": [100, 101, 102, 103],
                "volume": [1000, 1000, 1000, 1000],
                "open_interest": [5000, 5000, 5000, 5000],
            },
            index=idx,
        )
        signals = pd.DataFrame({"signal": ["观望", "观望", "观望", "观望"], "trade_edge": [0.0, 0.0, 0.0, 0.0]}, index=idx)
        result = run_futures_backtest(bars, signals, config=BacktestConfig())
        self.assertEqual(len(result["trades"]), 0)

    def test_low_data_quality_blocks_trade(self) -> None:
        idx = pd.date_range("2026-01-01", periods=4, freq="D")
        bars = pd.DataFrame(
            {
                "open": [100, 101, 102, 103],
                "high": [101, 102, 103, 104],
                "low": [99, 100, 101, 102],
                "close": [100, 101, 102, 103],
                "volume": [1000, 1000, 1000, 1000],
                "open_interest": [5000, 5000, 5000, 5000],
            },
            index=idx,
        )
        signals = pd.DataFrame({"signal": ["多头研究观察", 0, 0, 0], "trade_edge": [0.02, 0.0, 0.0, 0.0], "data_quality_score": [0.1, 0.1, 0.1, 0.1]}, index=idx)
        result = run_futures_backtest(bars, signals, config=BacktestConfig(no_trade_when_data_quality_low=0.45))
        self.assertEqual(len(result["trades"]), 0)


if __name__ == "__main__":
    unittest.main()
