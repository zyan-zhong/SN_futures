from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class EventSourceCoverageTest(unittest.TestCase):
    def test_config_declares_three_source_tiers(self) -> None:
        config_path = Path("config/event_sources.yaml")
        text = config_path.read_text(encoding="utf-8")
        for section in ("tier1_official", "tier2_industry", "tier3_market"):
            self.assertIn(section, text)
        for provider in ("shfe_public", "akshare_shmet", "newsapi", "alpha_vantage_news"):
            self.assertIn(provider, text)

    def test_provider_failure_does_not_clear_cached_events(self) -> None:
        old_env = os.environ.get("SN_INSIGHT_DATA_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            from sn_futures.event_store import ingest_articles, load_events, load_provider_status, update_provider_status

            inserted = ingest_articles(
                [
                    {
                        "title": "SHFE tin warehouse warrant declines",
                        "summary": "SHFE tin warehouse receipt decline is relevant to SN futures.",
                        "provider": "shfe_public",
                        "source": {"name": "SHFE"},
                        "url": "https://www.shfe.com.cn/tin-warrant",
                        "publishedAt": "2026-05-15T09:30:00+08:00",
                        "available_at": "2026-05-15T09:31:00+08:00",
                    }
                ],
                batch_id="source-coverage",
            )
            self.assertEqual(inserted, 1)
            self.assertEqual(len(load_events()), 1)

            update_provider_status(
                [
                    {
                        "provider": "newsapi",
                        "ok": False,
                        "message": "apiKeyInvalid",
                        "fetched_count": 0,
                        "rejected_count": 1,
                    }
                ]
            )
            self.assertEqual(len(load_events()), 1)
            statuses = {row["provider"]: row for row in load_provider_status()}
            self.assertIn("newsapi", statuses)
            self.assertIn("apiKeyInvalid", statuses["newsapi"].get("last_error", ""))
        if old_env is None:
            os.environ.pop("SN_INSIGHT_DATA_DIR", None)
        else:
            os.environ["SN_INSIGHT_DATA_DIR"] = old_env


if __name__ == "__main__":
    unittest.main()
