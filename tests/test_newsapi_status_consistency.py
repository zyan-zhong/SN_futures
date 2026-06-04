from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.provider_status_canonical_service import build_canonical_provider_status
from sn_futures.services.refresh_service import refresh_news_data


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class RateLimitedNewsProvider:
    def fetch_tin_news(self, **_: object) -> dict[str, object]:
        return {
            "configured": True,
            "enabled": True,
            "success": False,
            "articles": [],
            "error_code": "rate_limited",
            "message": "quota exceeded",
            "query_attempts": [],
        }


class NewsApiStatusConsistencyTest(unittest.TestCase):
    def test_newsapi_failure_with_last_good_cache_is_using_cache_not_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": "configured"}, clear=False):
            output = Path(tmp) / "outputs"
            cached_event = {
                "title": "SHFE tin inventory decline",
                "description": "Tin supply shock",
                "published_at": "2026-05-30T09:30:00Z",
                "source": "Reuters",
                "url": "https://example.com/tin",
                "used_in_model": True,
            }
            _write_json(output / "events" / "news_raw.json", {"articles": [cached_event], "generated_at": "2026-05-30T10:00:00"})
            _write_json(output / "events" / "news_events.json", {"events": [cached_event], "generated_at": "2026-05-30T10:00:00"})

            refresh = refresh_news_data(force=True, provider=RateLimitedNewsProvider())
            canonical = build_canonical_provider_status()

        newsapi = canonical["providers"]["newsapi"]
        self.assertEqual(refresh["status"], "using_cache")
        self.assertEqual(newsapi["status"], "using_cache")
        self.assertTrue(newsapi["from_cache"])
        self.assertEqual(newsapi["row_count"], 1)
        self.assertNotEqual(newsapi["status"], "error")


if __name__ == "__main__":
    unittest.main()
