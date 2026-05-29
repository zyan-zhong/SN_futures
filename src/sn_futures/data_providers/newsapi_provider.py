from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from ..api_clients import RateLimitedCacheClient
from ..config import load_project_env
from ..services.api_key_resolver import resolve_secret
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text


NEWS_QUERY_PROFILES: tuple[dict[str, str], ...] = (
    {
        "group": "core_english",
        "language": "en",
        "query": '("tin" OR "LME tin" OR "SHFE tin" OR "Shanghai tin") AND '
        "(futures OR price OR inventory OR supply OR demand OR smelter)",
    },
    {
        "group": "supply_asia",
        "language": "en",
        "query": '(tin AND (Indonesia OR Myanmar OR "Wa State" OR "Man Maw" OR smelter '
        "OR mining OR export OR quota OR suspension))",
    },
    {
        "group": "exchange",
        "language": "en",
        "query": '("LME tin" OR "SHFE tin" OR "Shanghai Futures Exchange tin" '
        'OR "tin inventory" OR "tin stockpiles")',
    },
    {
        "group": "demand",
        "language": "en",
        "query": "(tin AND (semiconductor OR solder OR photovoltaic OR solar OR electronics OR PCB))",
    },
    {
        "group": "chinese",
        "language": "zh",
        "query": '("沪锡" OR "锡期货" OR "上期所锡" OR "锡库存" OR "锡供应" OR "锡升贴水" OR "缅甸锡" OR "印尼锡")',
    },
)

ENGLISH_TIN_QUERIES: tuple[str, ...] = tuple(
    profile["query"] for profile in NEWS_QUERY_PROFILES if profile["language"] == "en"
)
CHINESE_TIN_QUERIES: tuple[str, ...] = tuple(
    profile["query"] for profile in NEWS_QUERY_PROFILES if profile["language"] == "zh"
)

NEWSAPI_VALIDATION_QUERY = (
    '("tin" OR "SHFE tin" OR "LME tin" OR "Shanghai tin") AND '
    "(futures OR inventory OR supply OR demand)"
)


class NewsApiProvider:
    """NewsAPI adapter for tin-related event monitoring.

    The API key is sent through ``X-Api-Key`` only. It is never placed in query
    parameters, returned payloads, or diagnostic request params.
    """

    name = "newsapi"
    base_url = "https://newsapi.org/v2/everything"

    def __init__(self, api_key: str | None = None, client: RateLimitedCacheClient | None = None) -> None:
        load_project_env()
        resolved = resolve_secret("SN_NEWSAPI_KEY")
        self.key_source = str(resolved.get("source") or "none")
        self.api_key = (api_key if api_key is not None else str(resolved.get("value") or "")).strip()
        if api_key is not None:
            self.key_source = "explicit"
        self.client = client or RateLimitedCacheClient()

    @staticmethod
    def _date_text(value: str | date | datetime | None) -> str | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value.date().isoformat()
        if isinstance(value, date):
            return value.isoformat()
        text = str(value).strip()
        return text or None

    @staticmethod
    def _default_window(days: int, to_date: str | date | datetime | None = None) -> tuple[str, str]:
        end_text = NewsApiProvider._date_text(to_date)
        end_date = datetime.fromisoformat(end_text).date() if end_text else datetime.now().date()
        start_date = end_date - timedelta(days=days)
        return start_date.isoformat(), end_date.isoformat()

    @staticmethod
    def _article_key(article: dict[str, Any]) -> str:
        url = str(article.get("url") or "").strip()
        title = str(article.get("title") or "").strip()
        published = str(article.get("publishedAt") or article.get("published_at") or "").strip()
        return url or f"{title}|{published}"

    def _disabled(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": False,
            "configured": False,
            "source": self.key_source,
            "attempted": False,
            "success": False,
            "from_cache": False,
            "message": "未配置 SN_NEWSAPI_KEY。NewsAPI is not configured.",
            "message_zh": "未配置 NewsAPI，无法拉取外部新闻。",
            "articles": [],
            "query_attempts": [],
            "row_count": 0,
            "error_code": "not_configured",
            "error_message_zh": "请在设置页配置 NewsAPI key，或继续使用本地缓存/样例模式。",
            "next_actions_zh": ["前往设置页配置 NewsAPI", "配置后点击刷新新闻"],
        }

    def _error(self, message: str, attempts: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        clean_message = sanitize_text(message)
        return {
            "name": self.name,
            "enabled": bool(self.api_key),
            "configured": bool(self.api_key),
            "source": self.key_source,
            "attempted": True,
            "success": False,
            "from_cache": False,
            "message": clean_message,
            "message_zh": f"NewsAPI 请求失败：{clean_message}",
            "articles": [],
            "query_attempts": attempts or [],
            "row_count": 0,
            "error_code": "request_failed",
            "error_message_zh": clean_message,
            "next_actions_zh": ["检查网络连接", "检查 NewsAPI key 是否有效", "稍后重试或查看刷新日志"],
        }

    def _fetch_one(
        self,
        *,
        query_group: str,
        query: str,
        language: str,
        start: str,
        end: str,
        sort_by: str,
        page_size: int,
        window_days: int,
    ) -> tuple[list[dict[str, Any]], bool, dict[str, Any]]:
        params: dict[str, Any] = {
            "q": query,
            "language": language,
            "from": start,
            "to": end,
            "sortBy": sort_by,
            "searchIn": "title,description",
            "pageSize": max(1, min(int(page_size), 100)),
        }
        attempt = {
            "query_group": query_group,
            "query": query,
            "language": language,
            "from": start,
            "to": end,
            "sortBy": sort_by,
            "window_days": window_days,
            "request_params_sanitized": dict(params),
            "status": "pending",
            "totalResults": 0,
            "returned_count": 0,
            "error": "",
        }
        headers = {
            "User-Agent": "SNInsightTerminal/3.1",
            "X-Api-Key": self.api_key,
        }
        try:
            response = self.client.fetch_json(
                source=self.name,
                url=self.base_url,
                params=params,
                headers=headers,
                ttl_seconds=300,
                min_interval_seconds=90,
                daily_limit=90,
            )
            payload = response.payload if isinstance(response.payload, dict) else {}
            articles = payload.get("articles", [])
            if not isinstance(articles, list):
                articles = []
            attempt["status"] = str(payload.get("status") or "ok")
            attempt["totalResults"] = int(payload.get("totalResults") or 0)
            attempt["returned_count"] = len(articles)
            enriched: list[dict[str, Any]] = []
            for item in articles:
                if not isinstance(item, dict):
                    continue
                enriched.append(
                    {
                        **item,
                        "query_group": query_group,
                        "query_language": language,
                        "query_sort_by": sort_by,
                        "query_window_days": window_days,
                    }
                )
            return enriched, bool(response.from_cache), attempt
        except Exception as exc:
            attempt["status"] = "error"
            attempt["error"] = sanitize_text(str(exc))
            return [], False, attempt

    def _query_plan(self, *, language: str, query: str | None = None) -> list[dict[str, str]]:
        if query:
            item_language = "en" if language == "all" else language
            return [{"group": "custom", "language": item_language, "query": query}]
        if language in {"en", "zh"}:
            return [profile for profile in NEWS_QUERY_PROFILES if profile["language"] == language]
        return list(NEWS_QUERY_PROFILES)

    def fetch_tin_news(
        self,
        *,
        from_date: str | date | datetime | None = None,
        to_date: str | date | datetime | None = None,
        language: str = "all",
        page_size: int = 50,
        query: str | None = None,
    ) -> dict[str, Any]:
        if not self.api_key:
            return self._disabled()

        start = self._date_text(from_date)
        end = self._date_text(to_date)
        explicit_window = bool(start and end)
        if not start or not end:
            start, end = self._default_window(7, to_date)

        plan = self._query_plan(language=language, query=query)
        windows: list[tuple[int, str, str]] = [(7, start, end)]
        if not explicit_window:
            fallback_start, fallback_end = self._default_window(30, to_date)
            if fallback_start != start or fallback_end != end:
                windows.append((30, fallback_start, fallback_end))
        sort_modes = ("relevancy", "publishedAt")

        all_articles: list[dict[str, Any]] = []
        query_attempts: list[dict[str, Any]] = []
        seen: set[str] = set()
        any_cache = False

        def run_profiles(
            profiles: list[dict[str, str]],
            *,
            window_days: int,
            window_start: str,
            window_end: str,
            sort_by: str,
        ) -> int:
            nonlocal any_cache
            new_count = 0
            for profile in profiles:
                articles, from_cache, attempt = self._fetch_one(
                    query_group=profile["group"],
                    query=profile["query"],
                    language=profile["language"],
                    start=window_start,
                    end=window_end,
                    sort_by=sort_by,
                    page_size=page_size,
                    window_days=window_days,
                )
                any_cache = any_cache or from_cache
                query_attempts.append(attempt)
                for article in articles:
                    key = self._article_key(article)
                    if key in seen:
                        continue
                    seen.add(key)
                    all_articles.append(article)
                    new_count += 1
            return new_count

        if query or language != "all" or explicit_window or not plan:
            active_plan = plan[:1] if explicit_window and not query and language == "all" else plan
            for window_days, window_start, window_end in windows:
                for sort_by in sort_modes:
                    run_profiles(
                        active_plan,
                        window_days=window_days,
                        window_start=window_start,
                        window_end=window_end,
                        sort_by=sort_by,
                    )
                    if all_articles:
                        break
                if all_articles:
                    break
        else:
            first_window_days, first_start, first_end = windows[0]
            core_plan = plan[:1]
            remaining_plan = plan[1:]
            run_profiles(core_plan, window_days=first_window_days, window_start=first_start, window_end=first_end, sort_by="relevancy")
            if not all_articles:
                run_profiles(
                    core_plan,
                    window_days=first_window_days,
                    window_start=first_start,
                    window_end=first_end,
                    sort_by="publishedAt",
                )
            if all_articles:
                supplement_days, supplement_start, supplement_end = (windows[1] if len(windows) > 1 else (30, *self._default_window(30, to_date)))
                run_profiles(
                    remaining_plan,
                    window_days=supplement_days,
                    window_start=supplement_start,
                    window_end=supplement_end,
                    sort_by="relevancy",
                )
            else:
                fallback_windows = windows[1:] or [(30, *self._default_window(30, to_date))]
                for window_days, window_start, window_end in fallback_windows:
                    for sort_by in sort_modes:
                        run_profiles(
                            plan,
                            window_days=window_days,
                            window_start=window_start,
                            window_end=window_end,
                            sort_by=sort_by,
                        )
                        if all_articles:
                            break
                    if all_articles:
                        break

        query_attempts = sanitize_mapping(query_attempts)
        failed_attempts = [item for item in query_attempts if isinstance(item, dict) and item.get("status") == "error"]
        if failed_attempts and len(failed_attempts) == len(query_attempts):
            return self._error("所有 NewsAPI 查询均失败。", query_attempts)

        now = datetime.now().isoformat()
        if not all_articles:
            message_zh = "NewsAPI 请求完成，但最近 7 天与 30 天回退窗口均未返回锡产业相关新闻。"
            next_actions = ["确认 NewsAPI 套餐和语言范围", "稍后刷新新闻", "必要时扩大关键词或时间窗口"]
        else:
            message_zh = f"NewsAPI 获取成功，返回 {len(all_articles)} 条锡相关候选新闻。"
            next_actions = ["查看事件监控", "刷新事件证据", "生成报告"]

        return {
            "name": self.name,
            "enabled": True,
            "configured": True,
            "source": self.key_source,
            "attempted": True,
            "success": True,
            "from_cache": any_cache,
            "message": message_zh,
            "message_zh": message_zh,
            "articles": all_articles,
            "query_attempts": query_attempts,
            "row_count": len(all_articles),
            "last_attempt_time": now,
            "last_success_time": now if all_articles else "",
            "error_code": "empty_result" if not all_articles else "",
            "error_message_zh": "返回为空。" if not all_articles else "",
            "next_actions_zh": next_actions,
        }


def fetch_newsapi_status() -> dict[str, Any]:
    return NewsApiProvider().fetch_tin_news(page_size=1)


def test_newsapi_connection(api_key: str | None = None) -> dict[str, Any]:
    provider = NewsApiProvider(api_key=api_key)
    if not provider.api_key:
        return {
            "configured": False,
            "source": provider.key_source,
            "success": False,
            "returned_count": 0,
            "total_results": 0,
            "rate_limited": False,
            "key_invalid": False,
            "last_success_time": "",
            "message_zh": "未配置 NewsAPI key。",
            "request_params_sanitized": {},
        }
    result = provider.fetch_tin_news(query=NEWSAPI_VALIDATION_QUERY, language="en", page_size=10)
    attempts = result.get("query_attempts") if isinstance(result.get("query_attempts"), list) else []
    error_text = sanitize_text(
        " ".join(str(item.get("error") or item.get("status") or "") for item in attempts if isinstance(item, dict))
    ).lower()
    rate_limited = "rate" in error_text or "limit" in error_text or "429" in error_text
    key_invalid = "invalid" in error_text or "api key" in error_text or "401" in error_text
    first_attempt = attempts[0] if attempts and isinstance(attempts[0], dict) else {}
    return {
        "configured": True,
        "source": provider.key_source,
        "success": bool(result.get("success")),
        "returned_count": int(result.get("row_count") or 0),
        "total_results": int(first_attempt.get("totalResults") or 0),
        "rate_limited": rate_limited,
        "key_invalid": key_invalid,
        "last_success_time": str(result.get("last_success_time") or ""),
        "message_zh": sanitize_text(str(result.get("message_zh") or "")),
        "request_params_sanitized": first_attempt.get("request_params_sanitized") or {},
    }
