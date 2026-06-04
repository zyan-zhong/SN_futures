from __future__ import annotations

import unittest

from sn_futures.services.model_stability_optimizer import optimize_stability_objective


class CandidateV7StabilityObjectiveTest(unittest.TestCase):
    def test_high_pbo_and_negative_cost_stress_raise_thresholds_and_reduce_complexity(self) -> None:
        result = optimize_stability_objective(
            candidate_version="v7",
            institutional_validation={
                "probability_of_backtest_overfitting": {"pbo": 0.85},
                "deflated_sharpe_ratio": {"deflated_sharpe_ratio": -0.2},
            },
            research_backtest={
                "horizons": {
                    "1d": {
                        "metrics": {
                            "turnover": 0.9,
                            "cost_stress": {
                                "2x_cost": {"expectancy": -0.0002},
                                "3x_cost": {"expectancy": -0.0004},
                            },
                        }
                    }
                }
            },
            feature_stability={"stability_score": 0.4, "passed": False},
        )

        self.assertEqual(result["candidate_version"], "v7")
        self.assertGreater(result["recommended_min_confidence"], 0.55)
        self.assertGreater(result["recommended_min_trade_edge"], 0.0002)
        self.assertIn("reduce_model_complexity", result["actions"])
        self.assertIn("reduce_trade_frequency", result["actions"])
        self.assertFalse(result["promotion_recommended"])


if __name__ == "__main__":
    unittest.main()
