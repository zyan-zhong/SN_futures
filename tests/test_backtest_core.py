from __future__ import annotations

import unittest
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.backtest_core import (
    BacktestConfig,
    CostConfig,
    build_walk_forward_windows,
    run_cost_sensitivity,
    run_futures_backtest,
    run_walk_forward_backtest,
)


def _bars() -> pd.DataFrame:
    index = pd.date_range("2026-01-01", periods=6, freq="D")
    return pd.DataFrame(
        {
            "open": [100, 100, 110, 108, 112, 115],
            "high": [101, 111, 112, 114, 116, 118],
            "low": [99, 99, 107, 106, 110, 113],
            "close": [100, 110, 108, 112, 115, 116],
            "volume": [1000, 1200, 900, 1100, 1300, 1250],
            "open_interest": [5000, 5100, 5050, 5200, 5300, 5280],
            "main_contract": ["sn2601", "sn2601", "sn2601", "sn2602", "sn2602", "sn2602"],
        },
        index=index,
    )


class BacktestCoreTests(unittest.TestCase):
    def test_signal_executes_on_next_bar(self) -> None:
        bars = _bars()
        signals = pd.DataFrame(0, index=bars.index, columns=["signal"])
        signals.loc[bars.index[0], "signal"] = 1
        signals["stop_loss"] = 80.0
        signals["take_profit"] = 200.0
        result = run_futures_backtest(
            bars,
            signals,
            config=BacktestConfig(cost=CostConfig(slippage_ticks=0, commission_per_contract=0, roll_cost_bps=0)),
        )
        trades = result["trades"]
        self.assertEqual(pd.Timestamp(trades.iloc[0]["entry_time"]), bars.index[1])
        self.assertEqual(float(trades.iloc[0]["entry_price"]), 100.0)

    def test_costs_reduce_net_profit(self) -> None:
        bars = _bars()
        signals = pd.DataFrame(0, index=bars.index, columns=["signal"])
        signals.loc[bars.index[0], "signal"] = 1
        signals["stop_loss"] = 80.0
        signals["take_profit"] = 200.0
        no_cost = run_futures_backtest(
            bars,
            signals,
            config=BacktestConfig(cost=CostConfig(slippage_ticks=0, commission_per_contract=0, roll_cost_bps=0)),
        )
        with_cost = run_futures_backtest(
            bars,
            signals,
            config=BacktestConfig(cost=CostConfig(slippage_ticks=1, commission_per_contract=5, roll_cost_bps=0)),
        )
        self.assertGreater(
            no_cost["metrics"]["net_profit_after_cost"],
            with_cost["metrics"]["net_profit_after_cost"],
        )

    def test_same_bar_double_trigger_uses_conservative_exit(self) -> None:
        index = pd.date_range("2026-01-01", periods=2, freq="D")
        bars = pd.DataFrame(
            {
                "open": [100, 100],
                "high": [101, 110],
                "low": [99, 90],
                "close": [100, 100],
                "volume": [1000, 1000],
                "open_interest": [5000, 5000],
            },
            index=index,
        )
        signals = pd.DataFrame({"signal": [1, 0], "stop_loss": [95.0, 95.0], "take_profit": [105.0, 105.0]}, index=index)
        result = run_futures_backtest(
            bars,
            signals,
            config=BacktestConfig(cost=CostConfig(slippage_ticks=0, commission_per_contract=0)),
        )
        trade = result["trades"].iloc[0]
        self.assertEqual(trade["exit_reason"], "both_conservative_stop")
        self.assertLess(float(trade["net_pnl"]), 0.0)

    def test_cost_sensitivity_runs_all_scenarios(self) -> None:
        bars = _bars()
        signals = pd.DataFrame(0, index=bars.index, columns=["signal"])
        signals.loc[bars.index[0], "signal"] = 1
        signals["stop_loss"] = 80.0
        signals["take_profit"] = 200.0
        sensitivity = run_cost_sensitivity(
            bars,
            signals,
            config=BacktestConfig(cost=CostConfig(slippage_ticks=1, commission_per_contract=2, roll_cost_bps=0)),
        )
        self.assertEqual(list(sensitivity["cost_multiplier"]), [0.5, 1.0, 2.0, 3.0])
        self.assertIn("positive_after_cost", sensitivity.columns)

    def test_walk_forward_windows_are_chronological(self) -> None:
        bars = _bars()
        windows = build_walk_forward_windows(bars.index, train_window=2, validation_window=1, test_window=1, step=1)
        self.assertGreaterEqual(len(windows), 1)
        first = windows[0]
        self.assertLess(first.train_end, first.validation_start)
        self.assertLess(first.validation_end, first.test_start)

    def test_walk_forward_backtest_uses_only_test_slice(self) -> None:
        bars = _bars()
        signals = pd.DataFrame(0, index=bars.index, columns=["signal"])
        signals.iloc[0, 0] = 1
        signals.iloc[3, 0] = 1
        wf = run_walk_forward_backtest(
            bars,
            signals,
            train_window=2,
            validation_window=1,
            test_window=2,
            step=1,
            config=BacktestConfig(cost=CostConfig(slippage_ticks=0, commission_per_contract=0, roll_cost_bps=0)),
        )
        self.assertGreaterEqual(wf["summary"]["window_count"], 1)
        for row in wf["windows"]:
            periods = row["periods"]
            self.assertLess(periods["train_end"], periods["validation_start"])
            self.assertLess(periods["validation_end"], periods["test_start"])


if __name__ == "__main__":
    unittest.main()
