from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.news_relevance_service import score_news_relevance


class NewsRelevanceV2Test(unittest.TestCase):
    def test_irrelevant_software_news_is_excluded(self) -> None:
        for title in [
            "Macworld covers a new Apple iPhone app",
            "PyPI package tin released for Python developers",
            "Sports entertainment app launches browser plugin",
        ]:
            score = score_news_relevance({"title": title, "source": "Tech"})
            self.assertLess(score["relevance_score"], 0.25)
            self.assertFalse(score["used_in_model"])
            self.assertEqual(score["category"], "irrelevant")

    def test_tin_supply_news_enters_model(self) -> None:
        score = score_news_relevance(
            {
                "title": "Myanmar Wa State tin concentrate supply disruption hits LME tin",
                "description": "SHFE tin inventory and smelter supply are watched by futures traders.",
            }
        )
        self.assertGreaterEqual(score["relevance_score"], 0.60)
        self.assertTrue(score["used_in_model"])
        self.assertEqual(score["category"], "supply")

    def test_chinese_shfe_tin_news_enters_model(self) -> None:
        score = score_news_relevance({"title": "沪锡库存下降，上期所锡供应偏紧", "description": "锡期货市场关注锡升贴水。"})
        self.assertGreaterEqual(score["relevance_score"], 0.60)
        self.assertTrue(score["used_in_model"])
        self.assertIn(score["category"], {"supply", "inventory"})


if __name__ == "__main__":
    unittest.main()
