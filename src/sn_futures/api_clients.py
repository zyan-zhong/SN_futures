from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import datetime
from hashlib import sha1
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from .runtime import get_user_data_dir
from .utils.secret_sanitizer import sanitize_mapping, sanitize_text, sanitize_url


@dataclass(frozen=True)
class CachedResponse:
    source: str
    url: str
    fetched_at: str
    from_cache: bool
    payload: Any


class RateLimitedCacheClient:
    def __init__(self) -> None:
        base = get_user_data_dir() / "cache"
        self.cache_dir = base / "http_cache"
        self.state_path = base / "rate_limit_state.json"
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {}
        try:
            return json.loads(self.state_path.read_text(encoding="utf-8"))
        except Exception:
            return {}

    def _save_state(self, state: dict[str, Any]) -> None:
        self.state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _header_identity(headers: dict[str, str] | None = None) -> dict[str, str]:
        identity: dict[str, str] = {}
        for key, value in (headers or {}).items():
            text = str(value or "")
            if not text:
                continue
            identity[str(key).lower()] = sha1(text.encode("utf-8")).hexdigest()
        return identity

    def _cache_path(
        self,
        source: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
    ) -> Path:
        raw = source + "|" + url + "|" + json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
        raw += "|" + json.dumps(self._header_identity(headers), sort_keys=True, ensure_ascii=False)
        return self.cache_dir / f"{sha1(raw.encode('utf-8')).hexdigest()}.json"

    def _read_cache(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            return None

    def _write_cache(self, path: Path, record: dict[str, Any]) -> None:
        path.write_text(json.dumps(sanitize_mapping(record), ensure_ascii=False, indent=2), encoding="utf-8")

    @staticmethod
    def _redact_url(url: str) -> str:
        return sanitize_url(url)

    @staticmethod
    def _payload_error_message(payload: Any) -> str:
        if not isinstance(payload, dict):
            return ""
        if payload.get("status") == "error":
            code = str(payload.get("code", "") or "api_error")
            message = sanitize_text(str(payload.get("message", "Remote API returned an error.")))
            return f"{code}: {message}"
        for key in ("Error Message", "Information", "Note"):
            if payload.get(key):
                return sanitize_text(str(payload.get(key)))
        return ""

    def fetch_json(
        self,
        source: str,
        url: str,
        params: dict[str, Any] | None = None,
        headers: dict[str, str] | None = None,
        ttl_seconds: int = 300,
        min_interval_seconds: int = 10,
        daily_limit: int = 100,
    ) -> CachedResponse:
        cache_path = self._cache_path(source, url, params, headers)
        now = datetime.now()
        state = self._load_state()
        state_seed = source + "|" + url + "|" + json.dumps(params or {}, sort_keys=True, ensure_ascii=False)
        state_seed += "|" + json.dumps(self._header_identity(headers), sort_keys=True, ensure_ascii=False)
        key = f"{source}:{sha1(state_seed.encode('utf-8')).hexdigest()[:10]}"
        today = now.strftime("%Y-%m-%d")
        record = state.get(key, {"date": today, "count": 0, "last_call_ts": 0.0})
        if record.get("date") != today:
            record = {"date": today, "count": 0, "last_call_ts": 0.0}

        cached = self._read_cache(cache_path)
        if cached is not None:
            cached_at = datetime.fromisoformat(cached["fetched_at"])
            cached_error = self._payload_error_message(cached.get("payload"))
            if (now - cached_at).total_seconds() <= ttl_seconds and not cached_error:
                return CachedResponse(
                    source=source,
                    url=url,
                    fetched_at=cached["fetched_at"],
                    from_cache=True,
                    payload=cached["payload"],
                )

        if record["count"] >= daily_limit:
            if cached is not None:
                cached_error = self._payload_error_message(cached.get("payload"))
                if cached_error:
                    raise RuntimeError(f"{source} daily limit reached; cached response is an API error: {cached_error}")
                return CachedResponse(
                    source=source,
                    url=url,
                    fetched_at=cached["fetched_at"],
                    from_cache=True,
                    payload=cached["payload"],
                )
            raise RuntimeError(f"{source} daily limit reached and no cache is available.")

        wait_seconds = min_interval_seconds - (time.time() - float(record.get("last_call_ts", 0.0)))
        if wait_seconds > 0 and cached is not None:
            cached_error = self._payload_error_message(cached.get("payload"))
            if cached_error:
                raise RuntimeError(f"{source} rate limited; cached response is an API error: {cached_error}")
            return CachedResponse(
                source=source,
                url=url,
                fetched_at=cached["fetched_at"],
                from_cache=True,
                payload=cached["payload"],
            )

        query = url
        if params:
            query = f"{url}?{urlencode(params)}"
        request = Request(query, headers=headers or {})
        try:
            with urlopen(request, timeout=20) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            try:
                parsed = json.loads(body) if body else {}
            except Exception:
                parsed = {}
            message = sanitize_text(
                str(parsed.get("message"))
                or str(parsed.get("Information"))
                or str(parsed.get("Error Message"))
                or body
                or f"HTTP Error {exc.code}"
            )
            code = str(parsed.get("code", "") or exc.code)
            raise RuntimeError(f"{code}: {message}") from exc

        fetched_at = now.isoformat()
        payload_error = self._payload_error_message(payload)
        if payload_error:
            record["count"] = int(record.get("count", 0)) + 1
            record["last_call_ts"] = time.time()
            record["date"] = today
            state[key] = record
            self._save_state(state)
            raise RuntimeError(payload_error)
        out = {"source": source, "url": self._redact_url(query), "fetched_at": fetched_at, "payload": payload}
        self._write_cache(cache_path, out)

        record["count"] = int(record.get("count", 0)) + 1
        record["last_call_ts"] = time.time()
        record["date"] = today
        state[key] = record
        self._save_state(state)
        return CachedResponse(source=source, url=self._redact_url(query), fetched_at=fetched_at, from_cache=False, payload=payload)

    def fetch_text(
        self,
        source: str,
        url: str,
        headers: dict[str, str] | None = None,
        ttl_seconds: int = 3,
        min_interval_seconds: int = 2,
        daily_limit: int = 2000,
        encoding: str = "gbk",
    ) -> CachedResponse:
        cache_path = self._cache_path(source, url, None, headers)
        now = datetime.now()
        state = self._load_state()
        state_seed = source + "|" + url + "|" + json.dumps(self._header_identity(headers), sort_keys=True, ensure_ascii=False)
        key = f"{source}:{sha1(state_seed.encode('utf-8')).hexdigest()[:10]}"
        today = now.strftime("%Y-%m-%d")
        record = state.get(key, {"date": today, "count": 0, "last_call_ts": 0.0})
        if record.get("date") != today:
            record = {"date": today, "count": 0, "last_call_ts": 0.0}

        cached = self._read_cache(cache_path)
        if cached is not None:
            cached_at = datetime.fromisoformat(cached["fetched_at"])
            if (now - cached_at).total_seconds() <= ttl_seconds:
                return CachedResponse(
                    source=source,
                    url=url,
                    fetched_at=cached["fetched_at"],
                    from_cache=True,
                    payload=cached["payload"],
                )

        if record["count"] >= daily_limit:
            if cached is not None:
                return CachedResponse(
                    source=source,
                    url=url,
                    fetched_at=cached["fetched_at"],
                    from_cache=True,
                    payload=cached["payload"],
                )
            raise RuntimeError(f"{source} daily limit reached and no cache is available.")

        if time.time() - float(record.get("last_call_ts", 0.0)) < min_interval_seconds and cached is not None:
            return CachedResponse(
                source=source,
                url=url,
                fetched_at=cached["fetched_at"],
                from_cache=True,
                payload=cached["payload"],
            )

        request = Request(url, headers=headers or {})
        try:
            with urlopen(request, timeout=15) as response:
                payload = response.read().decode(encoding, errors="ignore")
        except HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(body or f"HTTP Error {exc.code}") from exc

        fetched_at = now.isoformat()
        out = {"source": source, "url": self._redact_url(url), "fetched_at": fetched_at, "payload": payload}
        self._write_cache(cache_path, out)

        record["count"] = int(record.get("count", 0)) + 1
        record["last_call_ts"] = time.time()
        record["date"] = today
        state[key] = record
        self._save_state(state)
        return CachedResponse(source=source, url=self._redact_url(url), fetched_at=fetched_at, from_cache=False, payload=payload)


class AlphaVantageClient:
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None, client: RateLimitedCacheClient | None = None) -> None:
        self.api_key = api_key
        self.client = client or RateLimitedCacheClient()

    def enabled(self) -> bool:
        return bool(self.api_key)

    def query(self, function: str, **params: Any) -> CachedResponse:
        if not self.api_key:
            raise RuntimeError("Alpha Vantage API key not configured.")
        query = {"function": function, "apikey": self.api_key, **params}
        return self.client.fetch_json(
            source=f"alphavantage_{sha1(self.api_key.encode('utf-8')).hexdigest()[:8]}",
            url=self.BASE_URL,
            params=query,
            ttl_seconds=1800,
            min_interval_seconds=60,
            daily_limit=20,
        )

    def fetch_usd_cny_daily(self) -> CachedResponse:
        return self.query("FX_DAILY", from_symbol="USD", to_symbol="CNY", outputsize="compact")

    def fetch_treasury_10y(self) -> CachedResponse:
        return self.query("TREASURY_YIELD", interval="daily", maturity="10year")

    def fetch_macro_news(self, topics: str = "economy_monetary,fed,technology") -> CachedResponse:
        return self.query("NEWS_SENTIMENT", topics=topics, sort="LATEST", limit=20)


class NewsApiClient:
    BASE_URL = "https://newsapi.org/v2/everything"
    SOURCES_URL = "https://newsapi.org/v2/top-headlines/sources"

    def __init__(self, api_key: str | None, client: RateLimitedCacheClient | None = None) -> None:
        self.api_key = api_key
        self.client = client or RateLimitedCacheClient()

    def enabled(self) -> bool:
        return bool(self.api_key)

    def fetch_sources(self) -> CachedResponse:
        if not self.api_key:
            raise RuntimeError("NewsAPI key not configured.")
        headers = {"User-Agent": "SNInsightTerminal/2.0", "X-Api-Key": self.api_key}
        params = {"language": "en"}
        return self.client.fetch_json(
            source=f"newsapi_sources_{sha1(self.api_key.encode('utf-8')).hexdigest()[:8]}",
            url=self.SOURCES_URL,
            params=params,
            headers=headers,
            ttl_seconds=86400,
            min_interval_seconds=90,
            daily_limit=8,
        )

    def fetch_sn_news(
        self,
        query: str = (
            '"tin market" OR "LME tin" OR "SHFE tin" OR "Myanmar tin" OR "Indonesia tin" '
            'OR "tin ore" OR "tin concentrate" OR "tin smelter" OR "solder demand" '
            'OR "semiconductor solder" OR "solar photovoltaic tin"'
        ),
    ) -> CachedResponse:
        if not self.api_key:
            raise RuntimeError("NewsAPI key not configured.")
        headers = {"User-Agent": "SNInsightTerminal/2.0", "X-Api-Key": self.api_key}
        params = {"q": query, "language": "en", "sortBy": "publishedAt", "pageSize": 30}
        return self.client.fetch_json(
            source=f"newsapi_{sha1(self.api_key.encode('utf-8')).hexdigest()[:8]}",
            url=self.BASE_URL,
            params=params,
            headers=headers,
            ttl_seconds=300,
            min_interval_seconds=90,
            daily_limit=90,
        )


class SinaFinanceClient:
    BASE_URL = "https://hq.sinajs.cn/list="

    def __init__(self, client: RateLimitedCacheClient | None = None) -> None:
        self.client = client or RateLimitedCacheClient()

    def fetch_quotes(self, symbols: list[str]) -> CachedResponse:
        symbol_text = ",".join(symbols)
        url = self.BASE_URL + symbol_text
        headers = {"Referer": "https://finance.sina.com.cn/"}
        return self.client.fetch_text(
            source="sina_finance",
            url=url,
            headers=headers,
            ttl_seconds=2,
            min_interval_seconds=2,
            daily_limit=2000,
        )

    @staticmethod
    def parse_quotes(raw_text: str) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for line in raw_text.splitlines():
            if "=" not in line:
                continue
            left, right = line.split("=", 1)
            symbol = left.replace("var hq_str_", "").strip()
            payload = right.strip().strip(";").strip('"')
            fields = [item.strip() for item in payload.split(",")] if payload else []
            if not fields:
                continue
            rows.append(
                {
                    "symbol": symbol,
                    "name": fields[0],
                    "raw_fields": fields,
                    "raw_text": payload,
                }
            )
        return rows


def test_alpha_vantage_key(api_key: str) -> tuple[bool, str]:
    api_key = (api_key or "").strip()
    if not api_key:
        return False, "Alpha Vantage key is empty."
    try:
        response = AlphaVantageClient(api_key).fetch_usd_cny_daily()
        payload = response.payload if isinstance(response.payload, dict) else {}
        if "Error Message" in payload or "Information" in payload:
            return False, str(payload.get("Error Message") or payload.get("Information"))
        if "Note" in payload:
            return False, str(payload.get("Note"))
        return True, f"Alpha Vantage connected ({'cache' if response.from_cache else 'remote'})."
    except Exception as exc:
        return False, str(exc)


def test_newsapi_key(api_key: str) -> tuple[bool, str]:
    api_key = (api_key or "").strip()
    if not api_key:
        return False, "NewsAPI key is empty."
    try:
        client = NewsApiClient(api_key)
        response = client.fetch_sn_news(query='"tin market" OR "LME tin"')
        payload = response.payload if isinstance(response.payload, dict) else {}
        if payload.get("status") != "ok":
            return False, "NewsAPI returned an unexpected response."
        return True, f"NewsAPI connected ({'cache' if response.from_cache else 'remote'})."
    except Exception as exc:
        return False, str(exc)
