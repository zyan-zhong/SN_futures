from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.api_clients import CachedResponse
from sn_futures.data_providers.newsapi_unified_provider import NewsApiNewsProvider
from sn_futures.data_providers.provider_registry import build_provider_registry
from sn_futures.data_providers.sina_unified_provider import SinaRealtimeQuoteProvider


class FakeJsonClient:
    def __init__(self, payload: object, *, from_cache: bool = False, error: Exception | None = None) -> None:
        self.payload = payload
        self.from_cache = from_cache
        self.error = error
        self.calls: list[dict[str, object]] = []

    def fetch_json(self, **kwargs: object) -> CachedResponse:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return CachedResponse(
            source=str(kwargs.get("source") or ""),
            url=str(kwargs.get("url") or ""),
            fetched_at="2026-06-04T10:00:00",
            from_cache=self.from_cache,
            payload=self.payload,
        )


class FakeTextClient:
    def __init__(self, payload: str, *, from_cache: bool = False, error: Exception | None = None) -> None:
        self.payload = payload
        self.from_cache = from_cache
        self.error = error
        self.calls: list[dict[str, object]] = []

    def fetch_text(self, **kwargs: object) -> CachedResponse:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return CachedResponse(
            source=str(kwargs.get("source") or ""),
            url=str(kwargs.get("url") or ""),
            fetched_at="2026-06-04T10:00:00",
            from_cache=self.from_cache,
            payload=self.payload,
        )


class ProviderInterfaceContractTest(unittest.TestCase):
    def test_provider_result_and_manifest_never_return_raw_secret(self) -> None:
        secret = "news-secret-contract-value"
        client = FakeJsonClient({}, error=RuntimeError(f"Authorization Bearer {secret} apiKey={secret}"))
        provider = NewsApiNewsProvider(api_key=secret, client=client)

        result = provider.fetch()
        encoded = json.dumps(result.to_dict(), ensure_ascii=False)

        self.assertFalse(result.success)
        self.assertNotIn(secret, encoded)
        self.assertIn("***", encoded)

    def test_newsapi_api_error_is_not_success(self) -> None:
        client = FakeJsonClient({"status": "error", "code": "apiKeyInvalid", "message": "bad key"})
        provider = NewsApiNewsProvider(api_key="test-news-key", client=client)

        result = provider.fetch()

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "apiKeyInvalid")
        self.assertEqual(result.rows, [])
        self.assertEqual(result.normalized_rows, [])

    def test_cache_hit_is_marked_from_cache_in_result_status_and_manifest(self) -> None:
        raw = 'var hq_str_nf_SN0="沪锡连续,250000,249000,251000,248000,0,250100,0,250200,0,249900,0,249000,1234,5678";'
        client = FakeTextClient(raw, from_cache=True)
        provider = SinaRealtimeQuoteProvider(symbols=["nf_SN0"], client=client)

        result = provider.fetch()
        status = result.to_status()

        self.assertTrue(result.success)
        self.assertTrue(result.from_cache)
        self.assertTrue(status.from_cache)
        self.assertEqual(result.manifest["cache_status"], "cache")
        self.assertEqual(result.normalized_rows[0]["data_kind"], "realtime_quote")

    def test_malformed_sina_response_returns_structured_error(self) -> None:
        client = FakeTextClient("not a sina quote payload")
        provider = SinaRealtimeQuoteProvider(symbols=["nf_SN0"], client=client)

        result = provider.fetch()

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "malformed_response")
        self.assertEqual(result.rows, [])
        self.assertEqual(result.normalized_rows, [])
        self.assertIn("malformed", result.sanitized_error.lower())

    def test_provider_registry_exposes_first_migrated_local_providers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"SN_DATA_DIR": tmp}, clear=False):
            registry = build_provider_registry()

        self.assertIn("sina_realtime_quote", registry)
        self.assertIn("newsapi_news", registry)
        self.assertEqual(registry["sina_realtime_quote"].data_kind, "realtime_quote")
        self.assertEqual(registry["newsapi_news"].data_kind, "news")

    def test_canonical_provider_status_keeps_legacy_shape_and_exposes_registry(self) -> None:
        from sn_futures.services.provider_status_canonical_service import build_canonical_provider_status

        with tempfile.TemporaryDirectory() as tmp, patch.dict("os.environ", {"SN_DATA_DIR": tmp}, clear=False):
            payload = build_canonical_provider_status()

        self.assertIn("providers", payload)
        self.assertIn("provider_list", payload)
        self.assertEqual(payload["provider_interface_schema_version"], "provider-result-v1")
        provider_ids = {row["provider_id"] for row in payload["provider_registry"]}
        self.assertIn("sina_realtime_quote", provider_ids)
        self.assertIn("newsapi_news", provider_ids)


if __name__ == "__main__":
    unittest.main()
