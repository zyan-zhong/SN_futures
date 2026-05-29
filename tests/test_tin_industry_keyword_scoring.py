from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.news_relevance_service import score_news_relevance


class TinIndustryKeywordScoringTest(unittest.TestCase):
    def test_shfe_tin_futures_news_enters_model(self) -> None:
        result = score_news_relevance(
            {
                "title": "SHFE tin futures open interest rises as Shanghai tin price rallies",
                "description": "Volume and open interest in Shanghai tin futures increase with inventory tightness.",
                "url": "https://www.reuters.com/markets/commodities/shfe-tin-futures",
                "source": {"name": "Reuters"},
            }
        )

        self.assertTrue(result["used_in_model"])
        self.assertGreaterEqual(result["exchange_entity_score"], 0.3)
        self.assertGreaterEqual(result["hard_evidence_score"], 0.3)
        self.assertIn("SHFE tin", result["keyword_hits"])

    def test_indonesia_export_quota_news_enters_model(self) -> None:
        result = score_news_relevance(
            {
                "title": "Indonesia tin export quota delay tightens supply",
                "description": "Smelters expect fewer refined tin shipments after mining export permits slow.",
                "url": "https://www.mining.com/indonesia-tin-export-quota",
                "source": {"name": "Mining.com"},
            }
        )

        self.assertTrue(result["used_in_model"])
        self.assertEqual(result["category"], "supply")
        self.assertGreaterEqual(result["geography_supply_score"], 0.3)

    def test_myanmar_wa_state_supply_news_enters_model(self) -> None:
        result = score_news_relevance(
            {
                "title": "Myanmar Wa State tin mine suspension cuts supply",
                "description": "Man Maw tin mining disruption may affect smelter feedstock and SHFE tin sentiment.",
                "url": "https://www.kitco.com/news/myanmar-wa-state-tin",
                "source": {"name": "Kitco"},
            }
        )

        self.assertTrue(result["used_in_model"])
        self.assertEqual(result["category"], "supply")
        self.assertGreaterEqual(result["hard_evidence_score"], 0.3)

    def test_chinese_tin_industry_terms_enter_model(self) -> None:
        result = score_news_relevance(
            {
                "title": "沪锡期货上涨，上期所锡库存下降",
                "description": "锡升贴水走强，印尼锡出口配额和缅甸锡供应扰动受到关注。",
                "url": "https://www.shfe.com.cn/news/sn",
                "source": {"name": "上海期货交易所"},
            }
        )

        self.assertTrue(result["used_in_model"])
        self.assertIn(result["category"], {"supply", "inventory", "exchange"})
        self.assertGreaterEqual(result["commodity_entity_score"], 0.5)
        self.assertGreaterEqual(result["hard_evidence_score"], 0.3)
        self.assertTrue(any(hit in result["keyword_hits"] for hit in ["沪锡", "上期所锡", "锡库存", "锡升贴水"]))


if __name__ == "__main__":
    unittest.main()
