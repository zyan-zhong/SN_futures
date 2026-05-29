import unittest

from sn_futures.direction_ensemble import build_direction_ensemble


class DirectionProbabilityContractTest(unittest.TestCase):
    def test_three_way_probabilities_are_normalized(self):
        result = build_direction_ensemble(
            {
                "horizon": "tomorrow",
                "anchor_price": 420000,
                "price_center": 424200,
                "prob_up": 0.61,
                "core_drivers": ["成交量确认", "库存下降"],
            },
            news_policy={"summary": {"weighted_sentiment": 0.12, "confidence_weight": 0.5, "included_count": 3}},
            validation_profile={"effective_sample_count": 30, "direction_hit_rate": 0.57},
            data_quality_score=0.82,
            minute_data_available=True,
        )
        total = result["p_up"] + result["p_down"] + result["p_neutral"]
        self.assertAlmostEqual(total, 1.0, places=3)
        self.assertGreaterEqual(result["prob_up"], 0.0)
        self.assertLessEqual(result["prob_up"], 1.0)

    def test_candidate_conflict_downgrades_to_neutral(self):
        result = build_direction_ensemble(
            {
                "horizon": "next_5m",
                "anchor_price": 420000,
                "price_center": 420020,
                "prob_up": 0.505,
                "core_drivers": [],
            },
            news_policy={"summary": {"weighted_sentiment": 0.0, "confidence_weight": 0.0, "included_count": 0}},
            validation_profile={},
            data_quality_score=0.44,
            minute_data_available=False,
        )
        self.assertEqual(result["direction"], "neutral")
        self.assertGreater(result["p_neutral"], 0.5)
        self.assertTrue(result["downgrade_reasons"])


if __name__ == "__main__":
    unittest.main()
