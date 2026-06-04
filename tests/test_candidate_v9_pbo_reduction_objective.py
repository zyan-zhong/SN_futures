from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.regime_neutral_strategy_service import build_regime_neutral_strategy_policy


class CandidateV9PboReductionObjectiveTest(unittest.TestCase):
    def test_policy_declares_cpcv_like_pbo_target_without_more_complex_models(self) -> None:
        policy = build_regime_neutral_strategy_policy(
            v8_diagnostics={
                "pbo_attribution": {"summary": {"pbo": 0.6, "threshold": 0.2, "overfit_splits": 3}},
                "reality_check_bootstrap_summary": {"p_value": 0.0575},
                "regime_concentration_attribution": {"dominant_regime": "high_volatility", "dominant_contribution": 1.0},
            },
            v8_report={"stable_strategy_policy": {"complexity": {"models": ["hist_gradient_boosting", "random_forest"]}}},
        )

        objective = policy["objective"]
        cpcv = policy["cpcv_like_pbo_validation"]

        self.assertEqual(cpcv["mode"], "leave_one_fold_out_rank_with_regime_quota")
        self.assertEqual(cpcv["target_pbo"], 0.2)
        self.assertIn("PBO", objective["minimize"])
        self.assertIn("single_regime_concentration", objective["minimize"])
        self.assertTrue(policy["complexity"]["selection_only"])
        self.assertEqual(policy["complexity"]["new_model_families_added"], [])


if __name__ == "__main__":
    unittest.main()
