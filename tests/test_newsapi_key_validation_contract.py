from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.data_providers.newsapi_provider import NewsApiProvider


class FakeClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def fetch_json(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))

        class Response:
            from_cache = False
            payload = {"status": "ok", "totalResults": 1, "articles": [{"title": "tin", "url": "https://example.test/1", "publishedAt": "2026-05-25"}]}

        return Response()


class NewsApiKeyValidationContractTest(unittest.TestCase):
    def test_newsapi_uses_header_not_query_param(self) -> None:
        client = FakeClient()
        provider = NewsApiProvider(api_key="NEWS_TEST_1234567890", client=client)  # type: ignore[arg-type]
        result = provider.fetch_tin_news(query='tin OR "LME tin"', language="en", page_size=1)

        self.assertTrue(result["success"])
        call = client.calls[0]
        self.assertEqual((call["headers"] or {})["X-Api-Key"], "NEWS_TEST_1234567890")  # type: ignore[index]
        self.assertNotIn("apiKey", call["params"])  # type: ignore[operator]

    def test_newsapi_reads_user_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            path = os.path.join(tmp, "config", "secrets.json")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write('{"SN_NEWSAPI_KEY": "NEWS_USER_1234567890"}')
            provider = NewsApiProvider(client=FakeClient())  # type: ignore[arg-type]

        self.assertEqual(provider.api_key, "NEWS_USER_1234567890")


if __name__ == "__main__":
    unittest.main()

