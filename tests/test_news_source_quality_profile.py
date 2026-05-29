from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.services.news_source_quality_service import (
    build_source_quality_report,
    load_news_source_profiles,
    score_source_quality,
)


class NewsSourceQualityProfileTest(unittest.TestCase):
    def test_profile_defines_whitelist_and_blacklist_domains(self) -> None:
        profile = load_news_source_profiles()

        self.assertIn("mining.com", profile["whitelist_domains"])
        self.assertIn("kitco.com", profile["whitelist_domains"])
        self.assertIn("lme.com", profile["whitelist_domains"])
        self.assertIn("shfe.com.cn", profile["whitelist_domains"])
        self.assertIn("macworld.com", profile["blacklist_domains"])
        self.assertIn("pypi.org", profile["blacklist_domains"])

    def test_source_quality_scores_whitelisted_domain(self) -> None:
        result = score_source_quality(
            {
                "title": "LME tin inventory drops",
                "url": "https://www.mining.com/lme-tin-inventory-drops/",
                "source": {"name": "Mining.com"},
            }
        )

        self.assertEqual(result["source_domain"], "mining.com")
        self.assertGreaterEqual(result["source_reliability_score"], 0.7)
        self.assertGreaterEqual(result["domain_whitelist_score"], 0.5)
        self.assertLess(result["domain_blacklist_penalty"], 0.5)

    def test_source_quality_report_summarizes_domains(self) -> None:
        tmp = Path("test-output-news-source-quality")
        events_dir = tmp / "outputs" / "events"
        events_dir.mkdir(parents=True, exist_ok=True)
        try:
            (events_dir / "news_relevance_report.json").write_text(
                json.dumps(
                    {
                        "high_relevance_events": [
                            {
                                "title": "SHFE tin futures volume rises",
                                "url": "https://www.shfe.com.cn/news/tin",
                                "source": {"name": "SHFE"},
                                "query_group": "futures_price",
                                "used_in_model": True,
                                "relevance_score": 0.81,
                                "source_reliability_score": 0.8,
                            }
                        ],
                        "low_relevance_events": [],
                        "rejected_events": [],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            import os

            old = os.environ.get("SN_DATA_DIR")
            os.environ["SN_DATA_DIR"] = str(tmp)
            try:
                report = build_source_quality_report()
            finally:
                if old is None:
                    os.environ.pop("SN_DATA_DIR", None)
                else:
                    os.environ["SN_DATA_DIR"] = old
        finally:
            import shutil

            shutil.rmtree(tmp, ignore_errors=True)

        self.assertEqual(report["article_count"], 1)
        self.assertEqual(report["used_in_model_count"], 1)
        self.assertTrue(report["domains"])
        self.assertIn("source_reliability", report)


if __name__ == "__main__":
    unittest.main()
