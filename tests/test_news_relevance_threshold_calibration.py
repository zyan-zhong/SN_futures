from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.news_relevance_service import apply_news_relevance, score_news_relevance


class NewsRelevanceThresholdCalibrationTest(unittest.TestCase):
    def test_threshold_allows_real_tin_news_but_blocks_weak_mentions(self) -> None:
        high = score_news_relevance(
            {
                "title": "Tin smelters face Myanmar Wa State concentrate disruption",
                "description": "LME tin and SHFE tin supply chains are affected.",
            }
        )
        weak = score_news_relevance(
            {
                "title": "A tin-colored phone case becomes popular",
                "description": "Apple accessory review with no futures, inventory, or supply-chain evidence.",
            }
        )

        self.assertGreaterEqual(high["relevance_score"], 0.55)
        self.assertTrue(high["used_in_model"])
        self.assertFalse(weak["used_in_model"])
        self.assertLess(weak["relevance_score"], 0.25)

    def test_each_model_event_has_keyword_evidence(self) -> None:
        result = apply_news_relevance(
            [
                {
                    "title": "SHFE tin inventory falls as Indonesia tin export quota stalls",
                    "description": "Futures market monitors warehouse stockpiles.",
                    "source_published_at": "2026-01-02T09:00:00",
                },
                {
                    "title": "Tin can packaging demand rises",
                    "description": "Food packaging story.",
                },
            ]
        )

        self.assertEqual(result["used_in_model_count"], 1)
        event = result["high_relevance_events"][0]
        self.assertTrue(event["keyword_hits"])
        self.assertTrue(event["used_in_model"])
        self.assertLess(event["negative_keyword_penalty"], 0.4)
        self.assertTrue(result["rejected_events"])
        self.assertTrue(result["rejected_events"][0]["exclusion_reason"])


if __name__ == "__main__":
    unittest.main()
