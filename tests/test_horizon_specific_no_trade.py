from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.stable_strategy_policy_service import build_stable_strategy_policy


class HorizonSpecificNoTradeTest(unittest.TestCase):
    def test_high_vol_roll_stale_and_cost_pressure_filters_are_explicit(self) -> None:
        policy = build_stable_strategy_policy(
            source_candidate_version="v7",
            target_candidate_version="v8",
            horizon_metrics={
                "10d": {
                    "directional_accuracy": 0.55,
                    "naive_directional_accuracy": 0.50,
                    "brier_score": 0.21,
                    "cost_adjusted_expectancy": 0.002,
                    "max_drawdown_proxy": -0.10,
                    "atr_percentile_p95": 0.93,
                    "roll_period_exposure": 0.20,
                    "stale_data_rate": 0.08,
                    "cost_pressure_p95": 0.82,
                }
            },
            institutional_validation={},
            feature_stability={"stable_features": ["settlement_basis_to_close"], "unstable_features": []},
        )

        filters = set(policy["no_trade_filters"])
        self.assertIn("high_volatility", filters)
        self.assertIn("roll_period", filters)
        self.assertIn("stale_data", filters)
        self.assertIn("high_cost_pressure", filters)
        self.assertIn("low_confidence", filters)
        self.assertIn("low_edge", filters)
        self.assertEqual(policy["threshold_policy"]["coverage_targets"], ["top10", "top15"])
        self.assertGreaterEqual(policy["horizon_policy"]["10d"]["min_confidence"], policy["threshold_policy"]["min_confidence"])


if __name__ == "__main__":
    unittest.main()
