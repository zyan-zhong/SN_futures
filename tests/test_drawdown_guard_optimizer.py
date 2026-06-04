from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.stable_strategy_policy_service import build_stable_strategy_policy


class DrawdownGuardOptimizerTest(unittest.TestCase):
    def test_20d_high_drawdown_adds_guard_and_reduces_trade_rate(self) -> None:
        policy = build_stable_strategy_policy(
            source_candidate_version="v7",
            target_candidate_version="v8",
            horizon_metrics={
                "20d": {
                    "directional_accuracy": 0.58,
                    "naive_directional_accuracy": 0.50,
                    "brier_score": 0.19,
                    "cost_adjusted_expectancy": 0.003,
                    "max_drawdown_proxy": -0.46,
                    "turnover": 0.65,
                }
            },
            institutional_validation={
                "probability_of_backtest_overfitting": {"pbo": 1.0},
                "deflated_sharpe_ratio": {"deflated_sharpe_ratio": 0.0},
            },
            feature_stability={"stable_features": ["cost_pressure_score"], "unstable_features": []},
        )

        horizon = policy["horizon_policy"]["20d"]
        self.assertTrue(horizon["drawdown_guard"])
        self.assertIn("drawdown_proxy_high", horizon["reasons"])
        self.assertGreaterEqual(horizon["min_confidence"], 0.68)
        self.assertLessEqual(horizon["max_trade_rate"], 0.12)
        self.assertIn("drawdown_guard", policy["no_trade_filters"])
        self.assertIn("reduce_trade_frequency", policy["actions"])


if __name__ == "__main__":
    unittest.main()
