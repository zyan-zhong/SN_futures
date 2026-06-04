from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

from candidate_v6_research_fixtures import successful_candidate, successful_dataset, write_ready_v6_inputs
from sn_futures.services.candidate_v6_gated_research_service import run_candidate_v6_gated_research


class CandidateV6ResearchBacktestTest(unittest.TestCase):
    def test_research_backtest_outputs_v6_equity_drawdown_trades_and_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            write_ready_v6_inputs(output)

            def fake_backtest(**_: object) -> dict[str, object]:
                backtest_dir = output / "research_backtests" / "v6"
                backtest_dir.mkdir(parents=True, exist_ok=True)
                equity = backtest_dir / "equity_curve_1d.csv"
                drawdown = backtest_dir / "drawdown_curve_1d.csv"
                trades = backtest_dir / "trades_1d.csv"
                metrics = backtest_dir / "metrics_1d.json"
                equity.write_text("timestamp,equity\n2026-05-01,1.01\n", encoding="utf-8")
                drawdown.write_text("timestamp,drawdown\n2026-05-01,0.0\n", encoding="utf-8")
                trades.write_text("timestamp,position,strategy_return\n2026-05-01,1,0.01\n", encoding="utf-8")
                metrics.write_text(json.dumps({"status": "success", "trade_count": 1, "total_return": 0.01}), encoding="utf-8")
                return {
                    "status": "success",
                    "candidate_version": "v6",
                    "horizons": {
                        "1d": {
                            "status": "success",
                            "equity_curve_path": str(equity),
                            "drawdown_curve_path": str(drawdown),
                            "trades_path": str(trades),
                            "metrics_path": str(metrics),
                            "metrics": {"trade_count": 1, "total_return": 0.01},
                        }
                    },
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }

            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset", return_value=successful_dataset()), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training", return_value=successful_candidate(output)), \
                patch("sn_futures.services.candidate_v6_gated_research_service.get_oof_integrity_report", return_value={"status": "success"}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_research_backtest", side_effect=fake_backtest), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_institutional_validation", return_value={"status": "failed", "passed": False, "dry_run": True}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.promote_candidate", return_value={"status": "failed", "passed": False, "dry_run": True, "active_updated": False}):
                result = run_candidate_v6_gated_research(horizons=("1d",))

            horizon = result["research_backtest"]["horizons"]["1d"]
            self.assertEqual(horizon["status"], "success")
            for key in ("equity_curve_path", "drawdown_curve_path", "trades_path", "metrics_path"):
                self.assertTrue(Path(horizon[key]).exists(), key)
            self.assertFalse(result["research_backtest"]["active_updated"])
            self.assertFalse(result["research_backtest"]["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
