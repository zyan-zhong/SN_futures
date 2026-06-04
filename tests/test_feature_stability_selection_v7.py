from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.stable_strategy_policy_service import build_stable_strategy_policy


class FeatureStabilitySelectionV7Test(unittest.TestCase):
    def test_unstable_features_are_dropped_and_stable_features_are_kept(self) -> None:
        policy = build_stable_strategy_policy(
            source_candidate_version="v7",
            target_candidate_version="v8",
            horizon_metrics={"5d": {"directional_accuracy": 0.57, "naive_directional_accuracy": 0.5, "brier_score": 0.19}},
            institutional_validation={},
            feature_stability={
                "stable_features": ["fee_rate", "settlement_basis_to_close", "cost_pressure_score"],
                "unstable_features": ["member_net_position", "fold_chasing_noise"],
            },
        )

        selection = policy["feature_selection"]
        self.assertEqual(selection["policy"], "drop_fold_unstable_features")
        self.assertIn("fee_rate", selection["stable_features"])
        self.assertIn("member_net_position", selection["dropped_unstable_features"])
        self.assertNotIn("fold_chasing_noise", selection["selected_features"])
        self.assertIn("feature_stability_selection", policy["actions"])


if __name__ == "__main__":
    unittest.main()
