from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.news_relevance_service import score_news_relevance


class NewsRelevanceFalseNegativeTest(unittest.TestCase):
    def test_tin_supply_news_is_not_false_negative(self) -> None:
        result = score_news_relevance(
            {
                "title": "Indonesia tin export quota delay tightens LME tin supply",
                "description": "Smelters and SHFE tin futures traders monitor low inventory.",
                "source": "Metals Daily",
            }
        )

        self.assertTrue(result["used_in_model"])
        self.assertGreaterEqual(result["relevance_score"], 0.55)
        self.assertEqual(result["category"], "supply")
        self.assertIn("Indonesia", result["keyword_hits"])
        self.assertLess(result["negative_keyword_penalty"], 0.4)

    def test_chinese_shfe_tin_news_is_not_false_negative(self) -> None:
        result = score_news_relevance(
            {
                "title": "沪锡库存下降，上期所锡仓单走低",
                "description": "锡期货市场关注缅甸锡供应和锡升贴水变化。",
                "source": "中文金属资讯",
            }
        )

        self.assertTrue(result["used_in_model"])
        self.assertGreaterEqual(result["relevance_score"], 0.55)
        self.assertIn(result["category"], {"supply", "inventory", "exchange"})
        self.assertTrue(any(hit in result["keyword_hits"] for hit in ["沪锡", "锡期货", "上期所锡", "锡库存"]))

    def test_generic_tin_can_news_is_excluded(self) -> None:
        result = score_news_relevance(
            {
                "title": "Food brands redesign tin can packaging for summer",
                "description": "The article discusses home decor and canned food packaging.",
                "source": "Lifestyle",
            }
        )

        self.assertFalse(result["used_in_model"])
        self.assertLess(result["relevance_score"], 0.25)
        self.assertEqual(result["category"], "irrelevant")
        self.assertIn("tin can", result["negative_keyword_hits"])

    def test_macworld_and_pypi_are_excluded(self) -> None:
        for title in (
            "Macworld reviews an Apple audio DAC accessory",
            "PyPI package tin adds Python software plugin support",
        ):
            result = score_news_relevance({"title": title, "description": "generic software news"})
            self.assertFalse(result["used_in_model"])
            self.assertLess(result["relevance_score"], 0.25)
            self.assertEqual(result["category"], "irrelevant")
            self.assertTrue(result["negative_keyword_hits"])


if __name__ == "__main__":
    unittest.main()
