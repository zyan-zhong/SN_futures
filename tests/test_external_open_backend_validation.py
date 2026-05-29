from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, "src")

from sn_futures import event_store


class ExternalOpenBackendValidationTest(unittest.TestCase):
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

    def test_backend_allows_public_event_url(self) -> None:
        event_store.ingest_articles(
            [
                {
                    "title": "public source",
                    "source": "public",
                    "url": "https://not-trusted.example/article",
                    "summary": "tin",
                    "published_at": "2026-05-15T09:00:00+08:00",
                    "available_at": "2026-05-15T09:01:00+08:00",
                    "impact_score": 0.8,
                    "related_symbols": ["SN", "锡"],
                }
            ],
            batch_id="test",
        )
        event = event_store.load_events(limit=1)[0]
        resolved = event_store.resolve_event_url(event["event_id"])
        self.assertTrue(resolved["ok"])
        self.assertEqual(resolved["final_open_url"], "https://not-trusted.example/article")

    def test_backend_rejects_private_event_url(self) -> None:
        event_store.ingest_articles(
            [
                {
                    "title": "private source",
                    "source": "private",
                    "url": "http://127.0.0.1/article",
                    "summary": "tin",
                    "published_at": "2026-05-15T09:00:00+08:00",
                    "available_at": "2026-05-15T09:01:00+08:00",
                    "impact_score": 0.8,
                    "related_symbols": ["SN", "锡"],
                }
            ],
            batch_id="test-private",
        )
        event = event_store.load_events(limit=1)[0]
        resolved = event_store.resolve_event_url(event["event_id"])
        self.assertFalse(resolved["ok"])
        self.assertEqual(resolved["blocked_reason"], "unsafe_or_private_url")


if __name__ == "__main__":
    unittest.main()
