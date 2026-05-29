from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api
from sn_futures.data_providers.newsapi_provider import NewsApiProvider, test_newsapi_connection as run_newsapi_connection_test
from sn_futures.services.settings_service import get_key_diagnostics, get_terminal_settings_status


class FakeClient:
    def __init__(self, payload: dict[str, object] | None = None, error: Exception | None = None) -> None:
        self.calls: list[dict[str, object]] = []
        self.payload = payload or {
            "status": "ok",
            "totalResults": 1,
            "articles": [{"title": "LME tin inventory falls", "description": "SHFE tin supply watch", "url": "https://example.test/tin"}],
        }
        self.error = error

    def fetch_json(self, **kwargs: object) -> object:
        self.calls.append(dict(kwargs))
        if self.error:
            raise self.error

        class Response:
            from_cache = False

            def __init__(self, payload: dict[str, object]) -> None:
                self.payload = payload

        return Response(self.payload)


class NewsApiRuntimeValidationTest(unittest.TestCase):
    def test_settings_status_and_key_diagnostics_use_user_secret(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            secrets = Path(tmp) / "config" / "secrets.json"
            secrets.parent.mkdir(parents=True, exist_ok=True)
            secrets.write_text(json.dumps({"SN_NEWSAPI_KEY": "NEWS_USER_1234567890"}), encoding="utf-8")

            status = get_terminal_settings_status()
            diagnostics = get_key_diagnostics()

        self.assertTrue(status["newsapi_configured"])
        self.assertEqual(status["newsapi_source"], "user_secrets")
        self.assertNotIn("NEWS_USER_1234567890", json.dumps(status, ensure_ascii=False))
        self.assertTrue(diagnostics["newsapi"]["configured"])
        self.assertEqual(diagnostics["newsapi"]["source"], "user_secrets")
        self.assertNotIn("NEWS_USER_1234567890", json.dumps(diagnostics, ensure_ascii=False))

    def test_newsapi_key_can_be_read_from_env(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": "NEWS_ENV_1234567890"}, clear=False):
            provider = NewsApiProvider(client=FakeClient())  # type: ignore[arg-type]
            diagnostics = get_key_diagnostics()

        self.assertEqual(provider.key_source, "env")
        self.assertEqual(provider.api_key, "NEWS_ENV_1234567890")
        self.assertEqual(diagnostics["newsapi"]["source"], "env")

    def test_newsapi_request_uses_header_and_sanitized_params(self) -> None:
        client = FakeClient()
        provider = NewsApiProvider(api_key="NEWS_HEADER_1234567890", client=client)  # type: ignore[arg-type]
        result = provider.fetch_tin_news(page_size=10)

        self.assertTrue(result["success"])
        call = client.calls[0]
        self.assertEqual((call["headers"] or {})["X-Api-Key"], "NEWS_HEADER_1234567890")  # type: ignore[index]
        self.assertNotIn("apiKey", call["params"])  # type: ignore[operator]
        self.assertIn("searchIn", call["params"])  # type: ignore[operator]
        self.assertNotIn("NEWS_HEADER_1234567890", json.dumps(result, ensure_ascii=False))

    def test_test_connection_sanitizes_key_in_remote_error(self) -> None:
        client = FakeClient(error=RuntimeError("NewsAPI rejected apiKey=NEWS_SECRET_1234567890"))
        provider = NewsApiProvider(api_key="NEWS_SECRET_1234567890", client=client)  # type: ignore[arg-type]
        result = provider.fetch_tin_news(query='tin OR "LME tin"', language="en", page_size=1)

        payload = json.dumps(result, ensure_ascii=False)
        self.assertIn("***", payload)
        self.assertNotIn("NEWS_SECRET_1234567890", payload)

    def test_newsapi_endpoints_and_docs_are_available(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}
        self.assertIn("/api/terminal/newsapi/status", paths)
        self.assertIn("/api/terminal/newsapi/test", paths)
        self.assertIn("/api/terminal/events/relevance-report", paths)

        status_code, payload = handle_terminal_api("/api/terminal/newsapi/status", "GET")
        self.assertEqual(status_code, 200)
        self.assertIn("configured", payload)

        status_code, payload = handle_terminal_api("/api/terminal/newsapi/test", "POST", body="{}")
        self.assertEqual(status_code, 200)
        self.assertIn("configured", payload)


if __name__ == "__main__":
    unittest.main()
