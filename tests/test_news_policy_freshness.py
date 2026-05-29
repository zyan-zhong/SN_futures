from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from sn_futures.data_providers.newsapi_provider import NewsApiProvider
from sn_futures.services.freshness_policy import classify_freshness


@dataclass
class _Response:
    payload: dict
    from_cache: bool = False


class _FallbackClient:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    def fetch_json(self, **kwargs):
        params = kwargs["params"]
        self.calls.append(params)
        start = str(params.get("from"))
        sort_by = str(params.get("sortBy"))
        if sort_by == "publishedAt" and start >= (datetime.now().date() - timedelta(days=8)).isoformat():
            return _Response({"status": "ok", "totalResults": 0, "articles": []})
        return _Response(
            {
                "status": "ok",
                "totalResults": 1,
                "articles": [
                    {
                        "title": "Tin inventory update",
                        "url": "https://example.com/tin-inventory",
                        "publishedAt": datetime.now().isoformat(),
                    }
                ],
            }
        )


def test_newsapi_unconfigured_is_not_expired(monkeypatch) -> None:
    monkeypatch.delenv("SN_NEWSAPI_KEY", raising=False)
    result = NewsApiProvider(api_key="").fetch_tin_news()
    assert result["enabled"] is False
    assert result["configured"] is False
    assert result["attempted"] is False
    assert "未配置" in result["message_zh"]


def test_newsapi_falls_back_from_7_days_to_30_days() -> None:
    client = _FallbackClient()
    result = NewsApiProvider(api_key="TEST_NEWS_KEY", client=client).fetch_tin_news(page_size=50)
    assert result["success"] is True
    assert result["row_count"] == 1
    assert result["query_attempts"]
    starts = {call["from"] for call in client.calls}
    assert len(starts) >= 2


def test_newsapi_empty_result_has_chinese_reason() -> None:
    class EmptyClient:
        def fetch_json(self, **kwargs):
            return _Response({"status": "ok", "totalResults": 0, "articles": []})

    result = NewsApiProvider(api_key="TEST_NEWS_KEY", client=EmptyClient()).fetch_tin_news()
    assert result["success"] is True
    assert result["row_count"] == 0
    assert "未返回" in result["message_zh"]


def test_policy_ttl_is_weekly_not_intraday() -> None:
    recent = datetime.now() - timedelta(days=6)
    status = classify_freshness("miit_policy", recent.isoformat(), success=True, enabled=True)
    assert status["freshness_label"] == "正常"
    assert status["stale"] is False

    older = datetime.now() - timedelta(days=10)
    status = classify_freshness("miit_policy", older.isoformat(), success=True, enabled=True)
    assert status["freshness_label"] == "较旧但可参考"
    assert status["stale"] is False

    expired = datetime.now() - timedelta(days=31)
    status = classify_freshness("miit_policy", expired.isoformat(), success=True, enabled=True)
    assert status["freshness_label"] == "已过期"
    assert status["stale"] is True


def test_shfe_public_weekend_does_not_become_failed() -> None:
    old = datetime.now() - timedelta(days=4)
    status = classify_freshness("shfe_public", old.isoformat(), success=True, enabled=True, trading_session="weekend")
    assert status["freshness_label"] == "非交易时段等待更新"
    assert status["stale"] is False
