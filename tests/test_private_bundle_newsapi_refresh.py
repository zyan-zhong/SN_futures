from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


class FakeResponse:
    from_cache = False

    payload = {
        "status": "ok",
        "totalResults": 2,
        "articles": [
            {
                "title": "Myanmar Wa State tin concentrate supply disruption hits LME tin",
                "description": "SHFE tin inventory and smelter supply are watched by futures traders.",
                "url": "https://example.test/high",
                "publishedAt": "2026-05-29T01:00:00Z",
                "source": {"name": "Example Metals"},
            },
            {
                "title": "Macworld covers a new Apple plugin",
                "description": "Generic software news unrelated to tin futures.",
                "url": "https://example.test/low",
                "publishedAt": "2026-05-29T02:00:00Z",
                "source": {"name": "Tech"},
            },
        ],
    }


class PrivateBundleNewsApiRefreshTest(unittest.TestCase):
    def test_refresh_news_writes_raw_filtered_factor_and_provider_status(self) -> None:
        captured_calls: list[dict[str, object]] = []

        def fake_fetch_json(**kwargs: object) -> FakeResponse:
            captured_calls.append(dict(kwargs))
            return FakeResponse()

        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": "FAKE_NEWS_REFRESH_123456"},
            clear=False,
        ), patch("sn_futures.api_clients.RateLimitedCacheClient.fetch_json", side_effect=fake_fetch_json):
            status_code, result = handle_terminal_api("/api/terminal/refresh/news", "POST", body={"force": True})
            events_dir = Path(tmp) / "outputs" / "events"
            raw = json.loads((events_dir / "news_raw.json").read_text(encoding="utf-8"))
            filtered = json.loads((events_dir / "news_events_filtered.json").read_text(encoding="utf-8"))
            factor_inputs = json.loads((events_dir / "event_factor_inputs.json").read_text(encoding="utf-8"))
            relevance = json.loads((events_dir / "news_relevance_report.json").read_text(encoding="utf-8"))
            provider_status = json.loads((events_dir / "news_provider_status.json").read_text(encoding="utf-8"))

        dumped = json.dumps({"result": result, "raw": raw, "filtered": filtered, "factor": factor_inputs, "provider": provider_status}, ensure_ascii=False)
        self.assertEqual(status_code, 200)
        self.assertIn(result["status"], {"success", "failed"})
        self.assertTrue(captured_calls)
        first_call = captured_calls[0]
        self.assertIn("X-Api-Key", first_call["headers"])  # type: ignore[operator]
        self.assertNotIn("apiKey", first_call["params"])  # type: ignore[operator]
        self.assertIn("searchIn", first_call["params"])  # type: ignore[operator]
        self.assertEqual(len(raw["articles"]), 2)
        self.assertEqual(len(filtered["events"]), 1)
        self.assertEqual(factor_inputs["used_in_model_count"], 1)
        self.assertEqual(relevance["used_in_model_count"], 1)
        self.assertGreaterEqual(relevance["rejected_count"], 1)
        self.assertTrue(provider_status["providers"][0]["configured"])
        self.assertNotIn("FAKE_NEWS_REFRESH_123456", dumped)


if __name__ == "__main__":
    unittest.main()
