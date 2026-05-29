import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.api_clients import CachedResponse
from sn_futures.data_providers.alphavantage_provider import AlphaVantageProvider
from sn_futures.data_providers.newsapi_provider import NewsApiProvider
from sn_futures.data_validators import build_validation_report, display_missing


class FakeCacheClient:
    def __init__(self) -> None:
        self.calls = []

    def fetch_json(self, **kwargs):
        self.calls.append(kwargs)
        return CachedResponse(
            source=str(kwargs.get("source", "")),
            url=str(kwargs.get("url", "")),
            fetched_at="2026-05-18T00:00:00",
            from_cache=False,
            payload={"articles": [{"title": "LME tin inventory update"}]},
        )


class DataProviderAndValidatorTests(unittest.TestCase):
    def test_alpha_provider_missing_key_is_non_fatal(self) -> None:
        provider = AlphaVantageProvider(api_key="")
        result = provider.fetch_fx_daily()
        self.assertEqual(result["name"], "alphavantage")
        self.assertFalse(result["enabled"])
        self.assertFalse(result["success"])
        self.assertIn("未配置 SN_ALPHA_VANTAGE_KEY", result["message"])

    def test_newsapi_missing_key_is_non_fatal(self) -> None:
        provider = NewsApiProvider(api_key="")
        result = provider.fetch_tin_news()
        self.assertEqual(result["name"], "newsapi")
        self.assertFalse(result["enabled"])
        self.assertFalse(result["success"])
        self.assertEqual(result["articles"], [])
        self.assertIn("未配置 SN_NEWSAPI_KEY", result["message"])

    def test_newsapi_uses_header_not_url_query_for_key(self) -> None:
        fake = FakeCacheClient()
        provider = NewsApiProvider(api_key="secret-test-key", client=fake)  # test-only value, not a real key
        result = provider.fetch_tin_news(from_date="2026-05-01", to_date="2026-05-18", page_size=5)
        self.assertTrue(result["success"])
        self.assertEqual(len(fake.calls), 1)
        call = fake.calls[0]
        self.assertEqual(call["headers"].get("X-Api-Key"), "secret-test-key")
        self.assertNotIn("apiKey", call["params"])

    def test_validation_report_flags_missing_fields(self) -> None:
        frame = pd.DataFrame(
            {
                "close": [100.0, None],
                "high": [101.0, 102.0],
                "low": [99.0, 100.0],
                "volume": [10.0, 11.0],
            }
        )
        report = build_validation_report(frame)
        self.assertIn("open_interest", report.required_fields_missing)
        self.assertIn("main_contract", report.required_fields_missing)
        self.assertIn("usd_cny", report.important_fields_missing)
        self.assertLess(report.data_quality_score, 1.0)
        self.assertEqual(display_missing(float("nan")), "数据暂缺")


if __name__ == "__main__":
    unittest.main()

