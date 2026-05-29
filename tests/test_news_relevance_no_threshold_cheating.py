from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.news_relevance_service import score_news_relevance


class NewsRelevanceNoThresholdCheatingTest(unittest.TestCase):
    def test_plain_tin_without_hard_evidence_does_not_enter_even_if_score_is_displayable(self) -> None:
        result = score_news_relevance(
            {
                "title": "Tin mentioned in a generic gadget outlook",
                "description": "The article briefly mentions tin in a generic gadget trend without industry-chain evidence.",
                "url": "https://example.com/generic-electronics-outlook",
                "source": {"name": "Generic Business Blog"},
            }
        )

        self.assertFalse(result["used_in_model"])
        self.assertLess(result["hard_evidence_score"], 0.30)
        self.assertIn("exclusion_reason", result)

    def test_used_in_model_requires_keyword_evidence(self) -> None:
        result = score_news_relevance(
            {
                "title": "Commodity market update",
                "description": "Metals moved on macro data, but no commodity-specific industry chain evidence is present.",
                "url": "https://example.com/commodity-update",
                "source": {"name": "Reuters"},
            }
        )

        self.assertFalse(result["used_in_model"])
        self.assertFalse(result["keyword_hits"])
        self.assertLess(result["commodity_entity_score"], 0.1)


if __name__ == "__main__":
    unittest.main()
