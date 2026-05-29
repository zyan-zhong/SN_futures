from __future__ import annotations

import json
import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.position_scenario import BANNED_CERTAINTY_TERMS, evaluate_position_scenario


class PositionScenarioGuardrailsTest(unittest.TestCase):
    def test_position_scenario_is_non_prescriptive(self) -> None:
        payload = evaluate_position_scenario(
            {"position_direction": "long", "quantity": 1, "avg_price": 420000, "max_loss": 5000},
            {
                "cards": {
                    "tomorrow": {
                        "anchor_price": 421000,
                        "prob_up": 0.58,
                        "prob_down": 0.31,
                        "p_neutral": 0.11,
                        "confidence_score": 72,
                        "data_quality_score": 0.72,
                        "direction": "up",
                    }
                }
            },
        )
        text = json.dumps(payload, ensure_ascii=False)
        self.assertIn("不构成任何投资建议", text)
        for term in BANNED_CERTAINTY_TERMS:
            self.assertNotIn(term, text)
        self.assertGreaterEqual(len(payload["zones"]), 5)


if __name__ == "__main__":
    unittest.main()
