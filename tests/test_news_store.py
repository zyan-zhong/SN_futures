from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, "src")


class NewsStoreTest(unittest.TestCase):
    def test_append_only_and_url_resolution(self) -> None:
        old_env = os.environ.get("SN_INSIGHT_DATA_DIR")
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            from sn_futures.news_store import load_recent_articles, resolve_event_url, upsert_articles

            article = {
                "title": "缅甸锡矿供应扰动测试",
                "source": {"name": "测试源"},
                "url": "https://www.shmet.com/sn-news",
                "publishedAt": "2026-05-14T10:00:00+08:00",
                "summary": "锡矿供应扰动，沪锡相关。",
            }
            self.assertEqual(upsert_articles([article], fetch_batch_id="a"), 1)
            self.assertEqual(upsert_articles([], fetch_batch_id="failed"), 0)
            rows = load_recent_articles(limit=20)
            self.assertGreaterEqual(len(rows), 1)
            event_id = rows[0]["event_id"]
            resolved = resolve_event_url(event_id)
            self.assertTrue(resolved["ok"])
            self.assertEqual(resolved["url"], "https://www.shmet.com/sn-news")
        if old_env is None:
            os.environ.pop("SN_INSIGHT_DATA_DIR", None)
        else:
            os.environ["SN_INSIGHT_DATA_DIR"] = old_env


if __name__ == "__main__":
    unittest.main()
