from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Iterable

from ..api_clients import RateLimitedCacheClient
from ..config import load_project_env
from ..services.api_key_resolver import resolve_secret
from ..utils.secret_sanitizer import sanitize_text
from .base import BaseProvider


DEFAULT_NEWS_QUERY = (
    '("tin market" OR "LME tin" OR "SHFE tin" OR "Shanghai tin futures" OR '
    '"Myanmar tin" OR "Indonesia tin" OR "tin smelter")'
)


class NewsApiNewsProvider(BaseProvider):
    provider_id = "newsapi_news"
    data_kind = "news"
    source_url = "https://newsapi.org/v2/everything"
    raw_filename = "newsapi_news_raw.json"
    normalized_filename = "newsapi_news_normalized.json"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        client: RateLimitedCacheClient | None = None,
        query: str = DEFAULT_NEWS_QUERY,
        language: str = "en",
        page_size: int = 30,
    ) -> None:
        load_project_env()
        resolved = resolve_secret("SN_NEWSAPI_KEY")
        self.api_key = (api_key if api_key is not None else str(resolved.get("value") or "")).strip()
        self.key_source = "explicit" if api_key is not None else str(resolved.get("source") or "none")
        self.client = client or RateLimitedCacheClient()
        self.query = query
        self.language = language
        self.page_size = max(1, min(int(page_size), 100))

    def fetch_raw(self) -> Any:
        if not self.api_key:
            raise RuntimeError("SN_NEWSAPI_KEY not configured")
        end = datetime.now().date()
        start = end - timedelta(days=7)
        headers = {"User-Agent": "SNInsightTerminal/3.2", "X-Api-Key": self.api_key}
        params = {
            "q": self.query,
            "language": self.language,
            "from": start.isoformat(),
            "to": end.isoformat(),
            "sortBy": "publishedAt",
            "searchIn": "title,description",
            "pageSize": self.page_size,
        }
        return self.client.fetch_json(
            source=self.provider_id,
            url=self.source_url,
            params=params,
            headers=headers,
            ttl_seconds=300,
            min_interval_seconds=90,
            daily_limit=90,
        )

    def extract_rows(self, raw_response: Any) -> list[dict[str, Any]]:
        payload = getattr(raw_response, "payload", None)
        if not isinstance(payload, dict):
            raise ValueError("malformed NewsAPI response: payload is not JSON object")
        articles = payload.get("articles")
        if articles is None:
            return []
        if not isinstance(articles, list):
            raise ValueError("malformed NewsAPI response: articles is not a list")
        return [dict(row) for row in articles if isinstance(row, dict)]

    def normalize(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            source = row.get("source") if isinstance(row.get("source"), dict) else {}
            published = str(row.get("publishedAt") or row.get("published_at") or "")
            normalized.append(
                {
                    "provider_id": self.provider_id,
                    "data_kind": self.data_kind,
                    "title": str(row.get("title") or ""),
                    "description": str(row.get("description") or ""),
                    "url": str(row.get("url") or ""),
                    "source_name": str(source.get("name") or row.get("source_name") or ""),
                    "published_at": published,
                    "source_timestamp": published,
                    "sample_data_used": False,
                    "baseline_used": False,
                }
            )
        return normalized

    def validate(self, raw_response: Any, rows: list[dict[str, Any]], normalized_rows: list[dict[str, Any]]) -> dict[str, Any]:
        payload = getattr(raw_response, "payload", None)
        if not isinstance(payload, dict):
            return {
                "success": False,
                "error_code": "malformed_response",
                "sanitized_error": "malformed NewsAPI response",
            }
        if str(payload.get("status") or "ok").lower() == "error":
            code = str(payload.get("code") or "api_error")
            return {
                "success": False,
                "error_code": code,
                "status_code": code,
                "sanitized_error": sanitize_text(str(payload.get("message") or code), self.secret_values()),
            }
        return {"success": True, "status_code": str(payload.get("status") or "ok")}

    def secret_values(self) -> Iterable[str]:
        return (self.api_key,) if self.api_key else ()
