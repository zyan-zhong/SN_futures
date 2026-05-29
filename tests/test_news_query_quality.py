from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.data_providers.newsapi_provider import NEWS_QUERY_PROFILES, NewsApiProvider


class _FakeResponse:
    def __init__(self, payload: dict[str, object]) -> None:
        self.payload = payload
        self.from_cache = False


class NewsQueryQualityTest(unittest.TestCase):
    def test_query_profiles_cover_core_supply_exchange_demand_and_chinese(self) -> None:
        groups = {profile["group"] for profile in NEWS_QUERY_PROFILES}
        self.assertTrue({"core_english", "supply_asia", "exchange", "demand", "chinese"}.issubset(groups))
        chinese = next(profile for profile in NEWS_QUERY_PROFILES if profile["group"] == "chinese")
        self.assertEqual(chinese["language"], "zh")
        self.assertIn("沪锡", chinese["query"])
        self.assertIn("锡期货", chinese["query"])

    def test_seven_day_empty_result_falls_back_to_thirty_days(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_fetch_json(**kwargs: object) -> _FakeResponse:
            calls.append(dict(kwargs))
            params = kwargs["params"]  # type: ignore[index]
            if len(calls) < 3:
                return _FakeResponse({"status": "ok", "totalResults": 0, "articles": []})
            return _FakeResponse(
                {
                    "status": "ok",
                    "totalResults": 1,
                    "articles": [
                        {
                            "title": "LME tin inventory falls after Indonesia export suspension",
                            "description": "SHFE tin futures monitor supply.",
                            "url": "https://example.test/tin",
                            "publishedAt": "2026-05-20T00:00:00Z",
                            "source": {"name": "Metals"},
                        }
                    ],
                }
            )

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": "FAKE_NEWS_QUERY_123456"},
            clear=False,
        ), patch("sn_futures.api_clients.RateLimitedCacheClient.fetch_json", side_effect=fake_fetch_json):
            result = NewsApiProvider().fetch_tin_news(page_size=10)

        self.assertTrue(result["success"])
        self.assertEqual(result["row_count"], 1)
        self.assertGreaterEqual(len(calls), 3)
        windows = {(call["params"]["from"], call["params"]["to"]) for call in calls}  # type: ignore[index]
        self.assertGreaterEqual(len(windows), 2)
        self.assertIn("query_group", result["articles"][0])
        self.assertTrue(all("apiKey" not in call["params"] for call in calls))  # type: ignore[operator]
        self.assertTrue(all("X-Api-Key" in call["headers"] for call in calls))  # type: ignore[operator]

    def test_chinese_query_runs_when_english_queries_return_empty(self) -> None:
        calls: list[dict[str, object]] = []

        def fake_fetch_json(**kwargs: object) -> _FakeResponse:
            calls.append(dict(kwargs))
            params = kwargs["params"]  # type: ignore[index]
            if params.get("language") == "zh":
                return _FakeResponse(
                    {
                        "status": "ok",
                        "totalResults": 1,
                        "articles": [
                            {
                                "title": "沪锡库存下降 上期所锡仓单走低",
                                "description": "锡期货市场关注缅甸锡供应。",
                                "url": "https://example.test/zh",
                                "publishedAt": "2026-05-20T00:00:00Z",
                                "source": {"name": "中文金属"},
                            }
                        ],
                    }
                )
            return _FakeResponse({"status": "ok", "totalResults": 0, "articles": []})

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": "FAKE_NEWS_QUERY_123456"},
            clear=False,
        ), patch("sn_futures.api_clients.RateLimitedCacheClient.fetch_json", side_effect=fake_fetch_json):
            result = NewsApiProvider().fetch_tin_news(page_size=10)

        self.assertEqual(result["row_count"], 1)
        self.assertIn(result["articles"][0]["query_group"], {"chinese", "chinese_strict"})
        self.assertTrue(any(call["params"].get("language") == "zh" for call in calls))  # type: ignore[union-attr]


if __name__ == "__main__":
    unittest.main()
