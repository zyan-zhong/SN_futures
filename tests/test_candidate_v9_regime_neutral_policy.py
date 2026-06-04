from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.regime_neutral_strategy_service import build_regime_neutral_strategy_policy


class CandidateV9RegimeNeutralPolicyTest(unittest.TestCase):
    def test_high_single_regime_contribution_creates_regime_neutral_quota(self) -> None:
        policy = build_regime_neutral_strategy_policy(
            v8_diagnostics={
                "pbo_attribution": {"summary": {"pbo": 0.6, "threshold": 0.2}},
                "reality_check_bootstrap_summary": {"p_value": 0.0575, "threshold": 0.05},
                "regime_concentration_attribution": {
                    "dominant_regime": "high_volatility",
                    "dominant_contribution": 1.0,
                    "threshold": 0.7,
                },
                "trade_count_by_horizon": {"10d": 16, "20d": 71, "3d": 0, "5d": 0},
            },
            v8_report={
                "stable_strategy_policy": {
                    "complexity": {"models": ["hist_gradient_boosting", "random_forest", "huber_return"]}
                }
            },
        )

        self.assertEqual(policy["candidate_version"], "v9")
        self.assertEqual(policy["base_candidate"], "v8")
        self.assertTrue(policy["complexity"]["not_higher_than_v8"])
        self.assertLessEqual(policy["regime_trade_quota"]["max_single_regime_trade_share"], 0.55)
        self.assertIn("high_volatility", policy["regime_trade_quota"]["capped_regimes"])
        self.assertLessEqual(policy["fold_trade_quota"]["max_single_fold_trade_share"], 0.35)
        self.assertLessEqual(policy["year_trade_quota"]["max_single_year_trade_share"], 0.35)
        self.assertEqual(policy["cpcv_like_pbo_validation"]["target_pbo"], 0.2)
        self.assertFalse(policy["active_updated"])
        self.assertFalse(policy["customer_prediction_generated"])
        self.assertFalse(policy["promotion_gate_lowered"])


if __name__ == "__main__":
    unittest.main()
