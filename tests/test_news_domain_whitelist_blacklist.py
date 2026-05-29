from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.services.news_relevance_service import score_news_relevance


class NewsDomainWhitelistBlacklistTest(unittest.TestCase):
    def test_lme_tin_inventory_from_whitelisted_domain_enters_model(self) -> None:
        result = score_news_relevance(
            {
                "title": "LME tin inventory falls as warehouse stocks tighten",
                "description": "Tin stockpiles and warehouse warrants decline, supporting LME tin spreads.",
                "url": "https://www.lme.com/en/metals/non-ferrous/lme-tin/inventory-update",
                "source": {"name": "LME"},
            }
        )

        self.assertTrue(result["used_in_model"])
        self.assertGreaterEqual(result["relevance_score"], 0.60)
        self.assertGreaterEqual(result["hard_evidence_score"], 0.30)
        self.assertGreaterEqual(result["source_reliability_score"], 0.7)
        self.assertEqual(result["category"], "inventory")

    def test_blacklisted_apple_and_pypi_news_do_not_enter_model(self) -> None:
        examples = [
            {
                "title": "Macworld reviews Apple audio DAC in a tin box",
                "description": "Consumer gadget review with no commodity content.",
                "url": "https://www.macworld.com/article/apple-dac-review",
                "source": {"name": "Macworld"},
            },
            {
                "title": "PyPI package tin releases a Python software plugin",
                "description": "Generic software package update.",
                "url": "https://pypi.org/project/tin/",
                "source": {"name": "PyPI"},
            },
        ]

        for article in examples:
            result = score_news_relevance(article)
            self.assertFalse(result["used_in_model"])
            self.assertGreaterEqual(result["domain_blacklist_penalty"], 0.5)
            self.assertLess(result["relevance_score"], 0.25)


if __name__ == "__main__":
    unittest.main()
