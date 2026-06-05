from __future__ import annotations

import hashlib
import importlib
import re
from dataclasses import replace
from datetime import datetime
from typing import Any, Iterable, Mapping

import pandas as pd

from ..api_clients import CachedResponse
from ..api.json_utils import sanitize_for_json
from ..event_schema import EVENT_RECORD_SCHEMA_VERSION, source_tier, source_tier_weight
from ..services.news_relevance_service import score_news_relevance
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text
from .base import BaseProvider, ProviderResult


AKSHARE_NEWS_SCHEMA_VERSION = "akshare-news-provider-v1"
_LOCAL_PATH_RE = re.compile(r"[A-Za-z]:[\\/][^\s,;\"']+")


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_error(value: Any, extra_secrets: Iterable[str] = ()) -> str:
    text = sanitize_text(value, extra_secrets=extra_secrets)
    return _LOCAL_PATH_RE.sub("<local_path_redacted>", text)


def _content_hash(parts: Iterable[Any]) -> str:
    payload = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _pick(row: Mapping[str, Any], names: tuple[str, ...]) -> Any:
    lowered = {str(key).strip().lower(): value for key, value in row.items()}
    for name in names:
        if name in row:
            return row[name]
        lower = name.lower()
        if lower in lowered:
            return lowered[lower]
    return None


def _date_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return ""
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return pd.Timestamp(parsed).strftime("%Y-%m-%d")


def _time_text(value: Any) -> str:
    text = str(value or "").strip()
    if not text or text.lower() in {"nan", "none", "nat"}:
        return ""
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return pd.Timestamp(parsed).strftime("%H:%M:%S")


def _published_at(row: Mapping[str, Any]) -> str:
    direct = _pick(
        row,
        (
            "source_published_at",
            "published_at",
            "publishedAt",
            "发布时间",
            "发布日期时间",
            "datetime",
            "time",
        ),
    )
    direct_text = str(direct or "").strip()
    if direct_text and re.search(r"\d{4}", direct_text) and ("T" in direct_text or re.search(r"\d{2}:\d{2}", direct_text)):
        parsed = pd.to_datetime(direct_text, errors="coerce")
        if pd.notna(parsed):
            return pd.Timestamp(parsed).isoformat()
    date = _date_text(_pick(row, ("发布日期", "日期", "date", "publish_date", "time_published")))
    time = _time_text(_pick(row, ("发布时间", "时间", "time", "publish_time")))
    if date and time:
        return f"{date}T{time}+08:00"
    if date:
        return f"{date}T00:00:00+08:00"
    return ""


def _time_confidence(value: str) -> float:
    if not value:
        return 0.25
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return 0.40
    return 1.0


def _row_title(row: Mapping[str, Any]) -> str:
    return str(_pick(row, ("标题", "title", "新闻标题", "内容", "content")) or "").strip()


def _row_body(row: Mapping[str, Any]) -> str:
    return str(_pick(row, ("内容", "摘要", "summary", "description", "content", "新闻内容", "标题", "title")) or "").strip()


def _is_missing_required_columns(rows: list[dict[str, Any]]) -> bool:
    return bool(rows) and not any(_row_title(row) and _row_body(row) for row in rows)


def provider_articles_from_result(result: ProviderResult) -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    for row in result.normalized_rows:
        if not isinstance(row, Mapping):
            continue
        articles.append(
            {
                "title": row.get("title", ""),
                "description": row.get("summary", ""),
                "content": row.get("summary", ""),
                "url": row.get("url_sanitized", ""),
                "publishedAt": row.get("source_published_at", ""),
                "published_at": row.get("source_published_at", ""),
                "source_published_at": row.get("source_published_at", ""),
                "fetched_at": row.get("fetched_at", ""),
                "available_at": row.get("available_at", ""),
                "source": {"name": row.get("source", "")},
                "provider": row.get("provider", ""),
                "category": row.get("category", ""),
                "relevance_score": row.get("relevance_score", 0.0),
                "used_in_model": row.get("used_in_model", False),
                "event_id": row.get("event_id", ""),
                "content_hash": row.get("content_hash", ""),
            }
        )
    return sanitize_for_json(articles)


class AkShareNewsProvider(BaseProvider):
    provider_id = "akshare_news"
    data_kind = "news"
    source_url = "akshare://news/shmet+cls"
    raw_filename = "akshare_news_raw.json"
    normalized_filename = "akshare_news_normalized.json"

    def __init__(self, *, ak_module: Any | None = None, secret_values: Iterable[str] = ()) -> None:
        self.ak_module = ak_module
        self._secret_values = tuple(str(value) for value in secret_values if str(value or ""))

    def secret_values(self) -> Iterable[str]:
        return self._secret_values

    def classify_error(self, message: str) -> str:
        lower = str(message or "").lower()
        if "akshare_import_failed" in lower:
            return "akshare_import_failed"
        if "akshare_api_changed" in lower:
            return "akshare_api_changed"
        if "missing_required_columns" in lower:
            return "missing_required_columns"
        if "no_rows" in lower:
            return "no_rows"
        if "rate" in lower or "limit" in lower or "429" in lower:
            return "rate_limited"
        if "timeout" in lower or "connection" in lower or "network" in lower:
            return "network_failed"
        return "request_failed"

    def _akshare(self) -> Any:
        if self.ak_module is not None:
            return self.ak_module
        try:
            return importlib.import_module("akshare")
        except Exception as exc:
            raise RuntimeError(f"akshare_import_failed: {_safe_error(exc, self.secret_values())}") from exc

    def fetch_raw(self) -> CachedResponse:
        fetched_at = _now()
        ak = self._akshare()
        rows: list[dict[str, Any]] = []
        statuses: list[dict[str, Any]] = []
        seen: set[str] = set()
        for spec in self._source_specs():
            source_rows, status = self._fetch_source(ak, spec, fetched_at=fetched_at)
            statuses.append(status)
            for row in source_rows:
                key = "|".join([str(row.get("_akshare_provider") or ""), _row_title(row).lower(), str(row.get("_source_published_at") or "")[:16]])
                if key in seen:
                    continue
                seen.add(key)
                rows.append(row)
        return CachedResponse(
            source=self.provider_id,
            url=self.source_url,
            fetched_at=fetched_at,
            from_cache=False,
            payload={"rows": rows, "source_statuses": statuses},
        )

    def _source_specs(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "akshare_shmet_news",
                "provider": "akshare_shmet",
                "function": "futures_news_shmet",
                "url": "https://www.shmet.com/newsFlash/newsFlash.html?searchKeyword=%E9%94%A1",
                "params": [{"symbol": "锡"}, {"symbol": "小金属"}, {"symbol": "财经"}],
            },
            {
                "name": "akshare_cls_news",
                "provider": "akshare_cls",
                "function": "stock_info_global_cls",
                "url": "https://www.cls.cn/telegraph",
                "params": [{"symbol": "全部"}],
            },
        ]

    def _fetch_source(self, ak: Any, spec: Mapping[str, Any], *, fetched_at: str) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        function_name = str(spec["function"])
        provider = str(spec["provider"])
        fn = getattr(ak, function_name, None)
        if not callable(fn):
            return [], self._source_status(spec, fetched_at, success=False, error_code="akshare_api_changed", message=f"AKShare function missing: {function_name}")

        rows: list[dict[str, Any]] = []
        errors: list[str] = []
        for params in spec.get("params", []):
            try:
                payload = fn(**dict(params))
            except Exception as exc:
                errors.append(_safe_error(exc, self.secret_values()))
                continue
            frame = payload if isinstance(payload, pd.DataFrame) else pd.DataFrame(payload if isinstance(payload, list) else [])
            if frame.empty:
                continue
            for row in frame.to_dict(orient="records"):
                if not isinstance(row, Mapping):
                    continue
                item = dict(row)
                item["_akshare_provider"] = provider
                item["_akshare_source_name"] = str(spec["name"])
                item["_akshare_url"] = str(spec["url"])
                item["_source_published_at"] = _published_at(item)
                rows.append(item)

        if rows:
            return rows, self._source_status(spec, fetched_at, success=True, error_code="", row_count=len(rows), message=f"{function_name} returned {len(rows)} rows.")
        if errors:
            error_code = self.classify_error(" ".join(errors))
            return [], self._source_status(spec, fetched_at, success=False, error_code=error_code, message="; ".join(errors))
        return [], self._source_status(spec, fetched_at, success=False, error_code="no_rows", message=f"{function_name} returned no rows.")

    def _source_status(
        self,
        spec: Mapping[str, Any],
        fetched_at: str,
        *,
        success: bool,
        error_code: str,
        message: str,
        row_count: int = 0,
    ) -> dict[str, Any]:
        return {
            "name": str(spec.get("name") or spec.get("provider") or self.provider_id),
            "provider_id": str(spec.get("provider") or self.provider_id),
            "function_name": str(spec.get("function") or ""),
            "success": bool(success),
            "status_code": "success" if success else error_code,
            "error_code": "" if success else error_code,
            "row_count": int(row_count),
            "from_cache": False,
            "fetched_at": fetched_at,
            "message": _safe_error(message, self.secret_values()),
        }

    def extract_rows(self, raw_response: Any) -> list[dict[str, Any]]:
        payload = getattr(raw_response, "payload", None)
        if not isinstance(payload, Mapping):
            raise ValueError("malformed AkShare news response: payload is not object")
        rows = payload.get("rows")
        if not isinstance(rows, list):
            raise ValueError("malformed AkShare news response: rows is not list")
        return [dict(row) for row in rows if isinstance(row, Mapping)]

    def normalize(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            title = _row_title(row)
            body = _row_body(row)
            if not title or not body:
                continue
            provider = str(row.get("_akshare_provider") or self.provider_id)
            source = "SHMET" if provider == "akshare_shmet" else "CLS"
            published = str(row.get("_source_published_at") or "")
            fetched_at = _now()
            article = {
                "title": title[:300],
                "description": body[:1000],
                "content": body[:1000],
                "url": str(row.get("_akshare_url") or ""),
                "source": {"name": source},
                "provider": provider,
                "source_published_at": published,
                "published_at": published,
                "fetched_at": fetched_at,
                "available_at": published if _time_confidence(published) >= 0.5 else fetched_at,
            }
            score = score_news_relevance(article)
            confidence = _time_confidence(published)
            used = bool(score.get("used_in_model")) and confidence >= 0.5
            rejection_reason = "" if used else str(score.get("exclusion_reason") or ("missing_source_published_at" if confidence < 0.5 else "not_used_in_model"))
            event_id = _content_hash([title.lower(), str(row.get("_akshare_url") or ""), provider, published[:13]])[:24]
            tier = source_tier(provider, source)
            normalized.append(
                {
                    "event_record_schema_version": EVENT_RECORD_SCHEMA_VERSION,
                    "provider_id": self.provider_id,
                    "data_kind": self.data_kind,
                    "event_id": event_id,
                    "title": title[:300],
                    "summary": body[:1000],
                    "url_sanitized": str(row.get("_akshare_url") or ""),
                    "source": source,
                    "provider": provider,
                    "region": "China",
                    "category": str(score.get("category") or "irrelevant"),
                    "language": "zh" if re.search(r"[\u4e00-\u9fff]", f"{title} {body}") else "en",
                    "source_published_at": published,
                    "published_at": published,
                    "fetched_at": fetched_at,
                    "available_at": published if confidence >= 0.5 else fetched_at,
                    "event_time_confidence": confidence,
                    "relevance_score": float(score.get("relevance_score") or 0.0),
                    "source_reliability_score": float(score.get("source_reliability_score") or source_tier_weight(tier)),
                    "source_tier": tier,
                    "used_in_model": used,
                    "allowed_for_event_factor": used,
                    "rejection_reason": rejection_reason,
                    "content_hash": _content_hash([title, body, str(row.get("_akshare_url") or ""), published]),
                    "sample_data_used": False,
                    "baseline_used": False,
                    "source_timestamp": published,
                }
            )
        return sanitize_for_json(normalized)

    def validate(self, raw_response: Any, rows: list[dict[str, Any]], normalized_rows: list[dict[str, Any]]) -> dict[str, Any]:
        payload = getattr(raw_response, "payload", None)
        source_statuses = payload.get("source_statuses") if isinstance(payload, Mapping) else []
        if rows and not normalized_rows:
            error_code = "missing_required_columns" if _is_missing_required_columns(rows) else "no_relevant_rows"
            return {
                "success": False,
                "error_code": error_code,
                "status_code": error_code,
                "sanitized_error": f"{error_code}: AkShare news rows could not be normalized",
            }
        if normalized_rows:
            return {"success": True, "status_code": "success"}
        statuses = [dict(item) for item in source_statuses if isinstance(item, Mapping)] if isinstance(source_statuses, list) else []
        error_codes = [str(item.get("error_code") or item.get("status_code") or "") for item in statuses if item]
        if error_codes and all(code == "akshare_api_changed" for code in error_codes):
            code = "akshare_api_changed"
        elif any(code in {"rate_limited", "network_failed", "request_failed"} for code in error_codes):
            code = next(code for code in error_codes if code in {"rate_limited", "network_failed", "request_failed"})
        else:
            code = "no_rows"
        reason = "; ".join(str(item.get("message") or item.get("error_code") or "") for item in statuses if item.get("message") or item.get("error_code"))
        return {"success": False, "error_code": code, "status_code": code, "sanitized_error": f"{code}: {reason}"}

    def build_manifest(
        self,
        *,
        rows: list[dict[str, Any]],
        normalized_rows: list[dict[str, Any]],
        fetched_at: str,
        source_timestamp: str,
        from_cache: bool,
        stale: bool,
        rate_limited: bool,
        source_url_sanitized: str,
        raw_payload: Any,
    ) -> dict[str, Any]:
        manifest = super().build_manifest(
            rows=rows,
            normalized_rows=normalized_rows,
            fetched_at=fetched_at,
            source_timestamp=source_timestamp,
            from_cache=from_cache,
            stale=stale,
            rate_limited=rate_limited,
            source_url_sanitized=source_url_sanitized,
            raw_payload=raw_payload,
        )
        source_statuses = raw_payload.get("source_statuses") if isinstance(raw_payload, Mapping) else []
        published_count = sum(1 for row in normalized_rows if row.get("source_published_at"))
        normalized_count = len(normalized_rows)
        manifest.update(
            {
                "akshare_news_schema_version": AKSHARE_NEWS_SCHEMA_VERSION,
                "cache_status": "cache" if from_cache else ("remote" if rows or normalized_rows else "missing"),
                "source_published_at_coverage": round(published_count / normalized_count, 4) if normalized_count else 0.0,
                "source_statuses": source_statuses if isinstance(source_statuses, list) else [],
                "feature_store_written": False,
                "training_invoked": False,
                "backtest_invoked": False,
                "customer_prediction_generated": False,
            }
        )
        return sanitize_for_json(sanitize_mapping(manifest, self.secret_values()))

    def _error_result(self, **kwargs: Any) -> ProviderResult:
        sanitized = _safe_error(kwargs.get("sanitized_error") or kwargs.get("error_code") or "", self.secret_values())
        kwargs["sanitized_error"] = sanitized
        result = super()._error_result(**kwargs)
        manifest = dict(result.manifest)
        manifest.update(
            {
                "akshare_news_schema_version": AKSHARE_NEWS_SCHEMA_VERSION,
                "cache_status": "missing" if not result.rows else manifest.get("cache_status", "remote"),
                "feature_store_written": False,
                "training_invoked": False,
                "backtest_invoked": False,
                "customer_prediction_generated": False,
            }
        )
        return replace(result, manifest=sanitize_for_json(sanitize_mapping(manifest, self.secret_values())), sanitized_error=sanitized)
