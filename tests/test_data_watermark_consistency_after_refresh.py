from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.data_watermark_service import get_data_watermark_report
from sn_futures.services.provider_status_canonical_service import build_canonical_provider_status
from sn_futures.services.refresh_service import refresh_news_data


class SuccessfulNewsProvider:
    def fetch_tin_news(self, **_: object) -> dict[str, object]:
        return {
            "configured": True,
            "enabled": True,
            "success": True,
            "articles": [
                {
                    "title": "Tin supply update",
                    "description": "Tin inventory and supply chain update",
                    "publishedAt": "2026-05-31T09:30:00Z",
                    "source": {"name": "Reuters"},
                    "url": "https://example.com/tin-success",
                }
            ],
            "last_success_time": "2026-05-31T18:53:44",
            "message": "ok",
            "query_attempts": [],
        }


class DataWatermarkConsistencyAfterRefreshTest(unittest.TestCase):
    def test_news_watermark_matches_canonical_last_success_time_after_successful_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": "configured"}, clear=False):
            refresh_news_data(force=True, provider=SuccessfulNewsProvider())
            canonical = build_canonical_provider_status()
            watermark = get_data_watermark_report()

        newsapi = canonical["providers"]["newsapi"]
        self.assertEqual(newsapi["status"], "success")
        self.assertEqual(watermark["news_updated_at"], newsapi["last_success_time"])
        self.assertEqual(watermark["event_factor_updated_at"], newsapi["last_success_time"])
        self.assertEqual(watermark["provider_watermarks"]["newsapi"]["last_success_time"], newsapi["last_success_time"])


if __name__ == "__main__":
    unittest.main()
