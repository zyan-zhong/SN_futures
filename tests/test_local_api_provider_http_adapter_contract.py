from __future__ import annotations

import json
import os
import tempfile
import unittest
from dataclasses import dataclass
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.local_api_provider_http_adapter import LocalApiProviderHttpAdapter
from sn_futures.services.provider_smoke_test_service import run_provider_smoke_test


SECRET = "LOCAL_PROVIDER_TOKEN_1234567890"


@dataclass
class FakeHttpResponse:
    status_code: int
    payload: object


class FakeHttpClient:
    def __init__(self, response: FakeHttpResponse | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, object]] = []

    def get_json(self, url: str, *, headers: dict[str, str], timeout_seconds: int) -> FakeHttpResponse:
        self.calls.append({"url": url, "headers": headers, "timeout_seconds": timeout_seconds})
        if self.error:
            raise self.error
        if self.response is None:
            raise RuntimeError("no fake response configured")
        return self.response


def market_row() -> dict[str, object]:
    return {
        "symbol": "SN",
        "open": 200000.0,
        "high": 201000.0,
        "low": 199000.0,
        "close": 200500.0,
        "volume": 10,
        "source_timestamp": "2026-06-07T09:00:00",
    }


class LocalApiProviderHttpAdapterContractTest(unittest.TestCase):
    def test_missing_base_url_or_token_blocks_without_http_request(self) -> None:
        client = FakeHttpClient(FakeHttpResponse(200, {"rows": [market_row()]}))

        result = LocalApiProviderHttpAdapter(base_url="", token="", http_client=client).smoke()

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "local_provider_not_configured")
        self.assertEqual(client.calls, [])
        self.assertEqual(result.manifest["source_statuses"][0]["success"], False)
        self.assertEqual(result.manifest["source_statuses"][0]["error_code"], "local_provider_not_configured")

    def test_raw_authorization_headers_are_rejected_and_never_echoed(self) -> None:
        client = FakeHttpClient(FakeHttpResponse(200, {"rows": [market_row()]}))

        result = LocalApiProviderHttpAdapter(
            base_url="https://local-provider.example?token=raw-secret-token-123",
            token=SECRET,
            http_client=client,
            request_headers={"Authorization": "Bearer raw-secret-token-123"},
        ).smoke()

        serialized = json.dumps(result.to_dict(), ensure_ascii=False)
        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "raw_provider_credential_input_forbidden")
        self.assertNotIn(SECRET, serialized)
        self.assertNotIn("raw-secret-token-123", serialized)
        self.assertEqual(client.calls, [])

    def test_timeout_returns_structured_source_status(self) -> None:
        result = LocalApiProviderHttpAdapter(
            base_url="https://local-provider.example",
            token=SECRET,
            http_client=FakeHttpClient(error=TimeoutError("timeout with secret " + SECRET)),
        ).smoke()

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "request_timeout")
        status = result.manifest["source_statuses"][0]
        self.assertTrue(status["timed_out"])
        self.assertEqual(status["error_code"], "request_timeout")
        self.assertNotIn(SECRET, json.dumps(result.to_dict(), ensure_ascii=False))

    def test_http_401_403_are_unauthorized_without_key_leak(self) -> None:
        for code in (401, 403):
            result = LocalApiProviderHttpAdapter(
                base_url="https://local-provider.example",
                token=SECRET,
                http_client=FakeHttpClient(FakeHttpResponse(code, {"error": "bad key " + SECRET})),
            ).smoke()

            self.assertFalse(result.success)
            self.assertEqual(result.error_code, "unauthorized")
            self.assertEqual(result.status_code, str(code))
            self.assertNotIn(SECRET, json.dumps(result.to_dict(), ensure_ascii=False))

    def test_http_429_is_rate_limited(self) -> None:
        result = LocalApiProviderHttpAdapter(
            base_url="https://local-provider.example",
            token=SECRET,
            http_client=FakeHttpClient(FakeHttpResponse(429, {"error": "too many requests"})),
        ).smoke()

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "rate_limited")
        self.assertTrue(result.rate_limited)
        self.assertTrue(result.manifest["source_statuses"][0]["rate_limited"])

    def test_http_5xx_and_network_error_are_structured(self) -> None:
        server_error = LocalApiProviderHttpAdapter(
            base_url="https://local-provider.example",
            token=SECRET,
            http_client=FakeHttpClient(FakeHttpResponse(502, {"error": "upstream down"})),
        ).smoke()
        network_error = LocalApiProviderHttpAdapter(
            base_url="https://local-provider.example",
            token=SECRET,
            http_client=FakeHttpClient(error=OSError("network failed " + SECRET)),
        ).smoke()

        self.assertFalse(server_error.success)
        self.assertEqual(server_error.error_code, "request_failed")
        self.assertFalse(network_error.success)
        self.assertEqual(network_error.error_code, "network_failed")
        self.assertNotIn(SECRET, json.dumps(network_error.to_dict(), ensure_ascii=False))

    def test_empty_rows_malformed_json_and_missing_required_columns_do_not_pass(self) -> None:
        empty_rows = LocalApiProviderHttpAdapter(
            base_url="https://local-provider.example",
            token=SECRET,
            http_client=FakeHttpClient(FakeHttpResponse(200, {"rows": []})),
        ).smoke()
        malformed = LocalApiProviderHttpAdapter(
            base_url="https://local-provider.example",
            token=SECRET,
            http_client=FakeHttpClient(FakeHttpResponse(200, "not-json-object")),
        ).smoke()
        missing_columns = LocalApiProviderHttpAdapter(
            base_url="https://local-provider.example",
            token=SECRET,
            http_client=FakeHttpClient(FakeHttpResponse(200, {"rows": [{"symbol": "SN"}]})),
        ).smoke()

        self.assertEqual(empty_rows.error_code, "no_rows")
        self.assertEqual(malformed.error_code, "malformed_response")
        self.assertEqual(missing_columns.error_code, "missing_required_columns")
        self.assertEqual(missing_columns.normalized_rows, [])

    def test_valid_fake_market_rows_return_provider_result_manifest(self) -> None:
        result = LocalApiProviderHttpAdapter(
            base_url="https://local-provider.example",
            token=SECRET,
            data_kind="market_daily_bar",
            http_client=FakeHttpClient(FakeHttpResponse(200, {"rows": [market_row()]})),
        ).smoke()

        self.assertTrue(result.success)
        self.assertEqual(result.data_kind, "market_daily_bar")
        self.assertGreater(len(result.normalized_rows), 0)
        self.assertGreater(result.manifest["row_count"], 0)
        source_status = result.manifest["source_statuses"][0]
        self.assertEqual(source_status["source_id"], "local_api_provider")
        self.assertEqual(source_status["path"], "/smoke/market_daily_bar")
        self.assertEqual(source_status["schema"], "market_daily_bar")
        self.assertFalse(result.manifest["feature_store_written"])
        self.assertFalse(result.manifest["training_invoked"])
        self.assertFalse(result.manifest["backtest_invoked"])
        self.assertFalse(result.manifest["customer_prediction_generated"])

    def test_valid_fake_news_rows_are_supported_with_explicit_data_kind(self) -> None:
        row = {
            "title": "SHFE tin warehouse stocks update",
            "source": "SHFE",
            "source_published_at": "2026-06-07T10:00:00",
            "url": "https://example.test/news?id=1",
        }
        result = LocalApiProviderHttpAdapter(
            base_url="https://local-provider.example",
            token=SECRET,
            data_kind="news_event",
            http_client=FakeHttpClient(FakeHttpResponse(200, {"rows": [row]})),
        ).smoke()

        self.assertTrue(result.success)
        self.assertEqual(result.data_kind, "news_event")
        self.assertEqual(result.normalized_rows[0]["title"], row["title"])
        self.assertEqual(result.manifest["data_kind"], "news_event")

    def test_provider_smoke_service_uses_local_http_adapter_with_fake_client(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_LOCAL_API_PROVIDER_ENABLED": "true",
                "SN_LOCAL_API_PROVIDER_ID": "local_api_provider",
                "SN_LOCAL_API_PROVIDER_BASE_URL": "https://local-provider.example",
                "SN_LOCAL_API_PROVIDER_TOKEN": SECRET,
            },
            clear=True,
        ):
            success = run_provider_smoke_test(
                "local_api_provider",
                fake_http_client=FakeHttpClient(FakeHttpResponse(200, {"rows": [market_row()]})),
                data_kind="market_daily_bar",
                write=False,
            )
            failure = run_provider_smoke_test(
                "local_api_provider",
                fake_http_client=FakeHttpClient(error=TimeoutError("timeout " + SECRET)),
                data_kind="market_daily_bar",
                write=False,
            )

        self.assertEqual(success["status"], "pass")
        self.assertEqual(success["manifest"]["data_kind"], "market_daily_bar")
        self.assertEqual(success["source_statuses"][0]["schema"], "market_daily_bar")
        self.assertFalse(success["feature_store_written"])
        self.assertFalse(success["training_invoked"])
        self.assertFalse(success["backtest_invoked"])
        self.assertFalse(success["customer_prediction_generated"])
        self.assertEqual(failure["status"], "blocked")
        self.assertEqual(failure["error_code"], "request_timeout")
        self.assertTrue(failure["manifest"]["source_statuses"][0]["timed_out"])


if __name__ == "__main__":
    unittest.main()
