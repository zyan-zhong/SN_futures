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


def _write_oof(root: str, version: str = "v3", horizon: str = "1d") -> Path:
    path = Path(root) / "outputs" / "walk_forward" / version
    path.mkdir(parents=True, exist_ok=True)
    rows = []
    for idx in range(40):
        direction = 1 if idx % 3 else -1
        pred = direction if idx % 5 else -direction
        rows.append(
            {
                "candidate_version": version,
                "dataset_version": version,
                "horizon": horizon,
                "fold_id": str(1 + idx // 10),
                "timestamp": f"2026-01-{1 + idx:02d}",
                "label_start_time": f"2026-01-{1 + idx:02d}",
                "label_end_time": f"2026-01-{2 + idx:02d}",
                "realized_direction": direction,
                "realized_return": 0.004 * direction,
                "predicted_direction": pred,
                "confidence": 0.65 + (idx % 4) * 0.05,
                "trade_edge": 0.003,
                "selected_signal": "research_signal",
                "cost_assumption": 0.0002,
                "regime_label": "RANGE",
            }
        )
    out = path / f"oof_trace_{horizon}.csv"
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8")
    return out


class ResearchBacktestServiceTest(unittest.TestCase):
    def test_research_backtest_writes_equity_drawdown_trades_and_metrics_from_oof_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_oof(tmp, "v3", "1d")
            result = run_research_backtest(candidate_version="v3", horizons=("1d",))
            output = Path(tmp) / "outputs"
            active_exists = (output / "model_registry" / "active_model.json").exists()
            prediction_exists = (output / "sn_live_predictions.json").exists()
            horizon = result["horizons"]["1d"]
            equity_exists = Path(horizon["equity_curve_path"]).exists()
            drawdown_exists = Path(horizon["drawdown_curve_path"]).exists()
            trades_exists = Path(horizon["trades_path"]).exists()
            metrics_exists = Path(horizon["metrics_path"]).exists()

        self.assertEqual(result["status"], "success")
        self.assertFalse(active_exists)
        self.assertFalse(prediction_exists)
        self.assertTrue(equity_exists)
        self.assertTrue(drawdown_exists)
        self.assertTrue(trades_exists)
        self.assertTrue(metrics_exists)
        self.assertEqual(horizon["metrics"]["signal_source"], "oof_trace_only")
        self.assertGreater(horizon["metrics"]["trade_count"], 0)


if __name__ == "__main__":
    unittest.main()
