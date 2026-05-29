from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, "src")

from sn_futures import event_store


class ShmetArticleOpenFlowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.previous_env = os.environ.get("SN_INSIGHT_DATA_DIR")
        os.environ["SN_INSIGHT_DATA_DIR"] = self.tmp.name

    def tearDown(self) -> None:
        if self.previous_env is None:
            os.environ.pop("SN_INSIGHT_DATA_DIR", None)
        else:
            os.environ["SN_INSIGHT_DATA_DIR"] = self.previous_env
        self.tmp.cleanup()

    def test_backend_returns_final_open_url_for_shmet_article(self) -> None:
        count = event_store.ingest_articles(
            [
                {
                    "title": "SHMET tin market article",
                    "source": "SHMET",
                    "url": "https://news.shmet.com/article/2026/05/15/tin.html?from=sn",
                    "summary": "tin related",
                    "published_at": "2026-05-15T09:00:00+08:00",
                    "available_at": "2026-05-15T09:01:00+08:00",
                    "impact_score": 0.6,
                    "sentiment_score": 0.2,
                    "related_symbols": ["SN", "沪锡", "锡"],
                }
            ],
            batch_id="test",
        )
        self.assertEqual(count, 1)
        event = event_store.load_events(limit=1)[0]
        resolved = event_store.resolve_event_url(event["event_id"])
        self.assertTrue(resolved["ok"], resolved)
        self.assertEqual(resolved["final_open_url"], "https://news.shmet.com/article/2026/05/15/tin.html?from=sn")


if __name__ == "__main__":
    unittest.main()
