from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.stable_strategy_policy_service import build_stable_strategy_policy


class CandidateV7StabilityPolicyTest(unittest.TestCase):
    def test_weak_1d_horizon_becomes_research_only_without_prediction_or_active(self) -> None:
        policy = build_stable_strategy_policy(
            source_candidate_version="v7",
            target_candidate_version="v8",
            horizon_metrics={
                "1d": {
                    "directional_accuracy": 0.49,
                    "naive_directional_accuracy": 0.50,
                    "brier_score": 0.31,
                    "cost_adjusted_expectancy": -0.0001,
                    "max_drawdown_proxy": -0.08,
                },
                "5d": {
                    "directional_accuracy": 0.56,
                    "naive_directional_accuracy": 0.50,
                    "brier_score": 0.20,
                    "cost_adjusted_expectancy": 0.001,
                    "max_drawdown_proxy": -0.12,
                },
            },
            institutional_validation={
                "probability_of_backtest_overfitting": {"pbo": 1.0},
                "deflated_sharpe_ratio": {"deflated_sharpe_ratio": 0.0},
                "reality_check": {"p_value": 1.0},
            },
            feature_stability={"stable_features": ["fee_rate"], "unstable_features": ["noisy_signal"]},
        )

        self.assertEqual(policy["candidate_version"], "v8")
        self.assertEqual(policy["source_candidate_version"], "v7")
        self.assertFalse(policy["horizon_policy"]["1d"]["trade_enabled"])
        self.assertEqual(policy["horizon_policy"]["1d"]["action"], "research_only")
        self.assertIn("weak_direction_or_brier", policy["horizon_policy"]["1d"]["reasons"])
        self.assertTrue(policy["horizon_policy"]["5d"]["trade_enabled"])
        self.assertFalse(policy["active_updated"])
        self.assertFalse(policy["customer_prediction_generated"])
        self.assertFalse(policy["promotion_gate_lowered"])


if __name__ == "__main__":
    unittest.main()
