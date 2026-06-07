from __future__ import annotations

import json
import urllib.request
from datetime import datetime
from typing import Any, Mapping, Protocol

from ..api.json_utils import sanitize_for_json
from ..data_providers.base import PROVIDER_SCHEMA_VERSION, ProviderResult
from ..utils.secret_sanitizer import contains_secret_like_value, sanitize_mapping, sanitize_text, sanitize_url


ADAPTER_SCHEMA_VERSION = "local_api_provider_http_adapter_v1"
DEFAULT_TIMEOUT_SECONDS = 10
DATA_KIND_REQUIRED_COLUMNS: dict[str, set[str]] = {
    "market_daily_bar": {"symbol", "open", "high", "low", "close", "source_timestamp"},
    "news_event": {"title", "source", "source_published_at"},
}


class LocalProviderHttpClient(Protocol):
    def get_json(self, url: str, *, headers: dict[str, str], timeout_seconds: int) -> Any:
        ...


class UrllibJsonHttpClient:
    def get_json(self, url: str, *, headers: dict[str, str], timeout_seconds: int) -> dict[str, Any]:
        request = urllib.request.Request(url, headers=headers, method="GET")
        with urllib.request.urlopen(request, timeout=timeout_seconds) as response:  # noqa: S310 - explicit opt-in only.
            payload = json.loads(response.read().decode("utf-8"))
            return {"status_code": int(response.status), "payload": payload}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe(payload: Any, secrets: tuple[str, ...]) -> Any:
    return sanitize_for_json(sanitize_mapping(payload, secrets))


def _response_status_code(response: Any) -> str:
    if isinstance(response, Mapping):
        value = response.get("status_code") or response.get("status")
    else:
        value = getattr(response, "status_code", "") or getattr(response, "status", "")
    return str(value or "200")


def _response_payload(response: Any) -> Any:
    if isinstance(response, Mapping):
        if "payload" in response:
            return response.get("payload")
        if "json" in response:
            return response.get("json")
        return response
    return getattr(response, "payload", response)


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        rows = payload
    elif isinstance(payload, Mapping):
        if isinstance(payload.get("rows"), list):
            rows = payload.get("rows") or []
        elif isinstance(payload.get("data"), list):
            rows = payload.get("data") or []
        else:
            rows = []
    else:
        raise ValueError("malformed provider response")
    return [dict(row) for row in rows if isinstance(row, Mapping)]


class LocalApiProviderHttpAdapter:
    def __init__(
        self,
        *,
        provider_id: str = "local_api_provider",
        base_url: str = "",
        token: str = "",
        data_kind: str = "market_daily_bar",
        path: str = "",
        http_client: LocalProviderHttpClient | None = None,
        allow_remote: bool = False,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        request_headers: Mapping[str, Any] | None = None,
    ) -> None:
        self.provider_id = str(provider_id or "local_api_provider").strip().lower()
        self.base_url = str(base_url or "").strip()
        self.token = str(token or "").strip()
        self.data_kind = str(data_kind or "market_daily_bar").strip() or "market_daily_bar"
        self.path = str(path or f"/smoke/{self.data_kind}").strip()
        self.http_client = http_client
        self.allow_remote = bool(allow_remote)
        self.timeout_seconds = int(timeout_seconds or DEFAULT_TIMEOUT_SECONDS)
        self.request_headers = {str(key): value for key, value in dict(request_headers or {}).items()}

    def fetch_status(self) -> dict[str, Any]:
        result = self.smoke()
        return result.to_status().to_dict()

    def smoke_schema(self) -> dict[str, Any]:
        return {
            "schema_version": ADAPTER_SCHEMA_VERSION,
            "provider_id": self.provider_id,
            "data_kind": self.data_kind,
            "required_columns": sorted(DATA_KIND_REQUIRED_COLUMNS.get(self.data_kind, set())),
            "path": self.path,
        }

    def normalize_rows(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        required = DATA_KIND_REQUIRED_COLUMNS.get(self.data_kind, set())
        normalized: list[dict[str, Any]] = []
        for row in rows:
            cleaned = _safe(dict(row), self.secret_values())
            if not isinstance(cleaned, Mapping):
                continue
            normalized.append({key: cleaned.get(key) for key in sorted(set(cleaned) | required)})
        return normalized

    def build_manifest(
        self,
        *,
        status: str,
        error_code: str,
        status_code: str,
        rows: list[dict[str, Any]],
        normalized_rows: list[dict[str, Any]],
        fetched_at: str,
        source_statuses: list[dict[str, Any]],
        sanitized_error: str = "",
    ) -> dict[str, Any]:
        blocking_reasons = [error_code] if error_code else []
        return _safe(
            {
                "schema_version": ADAPTER_SCHEMA_VERSION,
                "provider_id": self.provider_id,
                "provider_mode": "local_api_provider",
                "data_kind": self.data_kind,
                "status": status,
                "status_code": status_code,
                "error_code": error_code,
                "fetched_at": fetched_at,
                "as_of": self._source_timestamp(normalized_rows) or fetched_at,
                "row_count": len(rows),
                "normalized_row_count": len(normalized_rows),
                "source_statuses": source_statuses,
                "source_url_sanitized": sanitize_url(self._url(), self.secret_values()),
                "blocking_reasons": blocking_reasons,
                "sanitized_error": sanitized_error,
                "sample_data_used": False,
                "baseline_used": False,
                "feature_store_written": False,
                "production_cache_written": False,
                "training_invoked": False,
                "backtest_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
            },
            self.secret_values(),
        )

    def to_provider_result(self, result: ProviderResult) -> ProviderResult:
        return result

    def smoke(self) -> ProviderResult:
        fetched_at = _now()
        if not self.base_url or not self.token:
            return self._error_result("local_provider_not_configured", fetched_at=fetched_at)
        if self._has_forbidden_raw_headers():
            return self._error_result("raw_provider_credential_input_forbidden", fetched_at=fetched_at)
        if self.http_client is None and not self.allow_remote:
            return self._error_result("remote_http_disabled", fetched_at=fetched_at)

        client = self.http_client or UrllibJsonHttpClient()
        try:
            response = client.get_json(self._url(), headers=self._headers(), timeout_seconds=self.timeout_seconds)
        except TimeoutError as exc:
            return self._error_result("request_timeout", fetched_at=fetched_at, sanitized_error=str(exc), timed_out=True)
        except OSError as exc:
            return self._error_result("network_failed", fetched_at=fetched_at, sanitized_error=str(exc))
        except Exception as exc:
            return self._error_result("request_failed", fetched_at=fetched_at, sanitized_error=str(exc))

        status_code = _response_status_code(response)
        payload = _response_payload(response)
        error_code = self._http_error_code(status_code)
        if error_code:
            return self._error_result(
                error_code,
                fetched_at=fetched_at,
                status_code=status_code,
                sanitized_error=json.dumps(_safe(payload, self.secret_values()), ensure_ascii=False, default=str),
                rate_limited=error_code == "rate_limited",
            )

        try:
            rows = _rows_from_payload(payload)
        except Exception as exc:
            return self._error_result("malformed_response", fetched_at=fetched_at, status_code=status_code, sanitized_error=str(exc))

        if not rows:
            return self._error_result("no_rows", fetched_at=fetched_at, status_code=status_code)

        missing = self._missing_required_columns(rows)
        if missing:
            return self._error_result(
                "missing_required_columns",
                fetched_at=fetched_at,
                status_code=status_code,
                rows=rows,
                sanitized_error=f"missing required columns: {', '.join(missing)}",
            )

        normalized_rows = self.normalize_rows(rows)
        source_status = self._source_status(success=True, row_count=len(rows), status_code=status_code)
        manifest = self.build_manifest(
            status="pass",
            error_code="",
            status_code=status_code,
            rows=rows,
            normalized_rows=normalized_rows,
            fetched_at=fetched_at,
            source_statuses=[source_status],
        )
        return ProviderResult(
            provider_id=self.provider_id,
            data_kind=self.data_kind,
            success=True,
            status_code=status_code,
            error_code="",
            rows=[dict(row) for row in rows],
            normalized_rows=[dict(row) for row in normalized_rows],
            fetched_at=fetched_at,
            source_timestamp=self._source_timestamp(normalized_rows),
            as_of=self._source_timestamp(normalized_rows) or fetched_at,
            from_cache=False,
            stale=False,
            rate_limited=False,
            schema_version=PROVIDER_SCHEMA_VERSION,
            manifest=manifest,
            sanitized_error="",
        )

    def _error_result(
        self,
        error_code: str,
        *,
        fetched_at: str,
        status_code: str = "",
        rows: list[dict[str, Any]] | None = None,
        sanitized_error: str = "",
        timed_out: bool = False,
        rate_limited: bool = False,
    ) -> ProviderResult:
        row_values = [dict(row) for row in (rows or [])]
        source_status = self._source_status(
            success=False,
            row_count=len(row_values),
            error_code=error_code,
            status_code=status_code,
            error_message=sanitized_error or error_code,
            timed_out=timed_out,
            rate_limited=rate_limited,
        )
        safe_error = sanitize_text(sanitized_error or error_code, self.secret_values())
        manifest = self.build_manifest(
            status="blocked",
            error_code=error_code,
            status_code=status_code,
            rows=row_values,
            normalized_rows=[],
            fetched_at=fetched_at,
            source_statuses=[source_status],
            sanitized_error=safe_error,
        )
        return ProviderResult(
            provider_id=self.provider_id,
            data_kind=self.data_kind,
            success=False,
            status_code=status_code,
            error_code=error_code,
            rows=row_values,
            normalized_rows=[],
            fetched_at=fetched_at,
            source_timestamp="",
            as_of="",
            from_cache=False,
            stale=False,
            rate_limited=rate_limited,
            schema_version=PROVIDER_SCHEMA_VERSION,
            manifest=manifest,
            sanitized_error=safe_error,
        )

    def _source_status(
        self,
        *,
        success: bool,
        row_count: int,
        error_code: str = "",
        status_code: str = "",
        error_message: str = "",
        timed_out: bool = False,
        rate_limited: bool = False,
    ) -> dict[str, Any]:
        return _safe(
            {
                "source_id": self.provider_id,
                "provider_id": self.provider_id,
                "function_name": "GET",
                "path": self.path,
                "schema": self.data_kind,
                "source_url_sanitized": sanitize_url(self._url(), self.secret_values()),
                "success": success,
                "row_count": row_count,
                "status_code": str(status_code or ""),
                "error_code": error_code,
                "error_message_sanitized": sanitize_text(error_message, self.secret_values()),
                "timed_out": timed_out,
                "rate_limited": rate_limited,
            },
            self.secret_values(),
        )

    def _headers(self) -> dict[str, str]:
        return {
            "Accept": "application/json",
            "Authorization": f"Bearer {self.token}",
        }

    def _has_forbidden_raw_headers(self) -> bool:
        for key, value in self.request_headers.items():
            lower = str(key or "").lower()
            if any(hint in lower for hint in ("authorization", "token", "secret", "password", "key")):
                return True
            if contains_secret_like_value(value):
                return True
        return False

    def _url(self) -> str:
        return f"{self.base_url.rstrip('/')}/{self.path.lstrip('/')}"

    def _http_error_code(self, status_code: str) -> str:
        try:
            code = int(status_code or 200)
        except Exception:
            return "request_failed"
        if code in {401, 403}:
            return "unauthorized"
        if code == 429:
            return "rate_limited"
        if code < 200 or code >= 300:
            return "request_failed"
        return ""

    def _missing_required_columns(self, rows: list[dict[str, Any]]) -> list[str]:
        required = DATA_KIND_REQUIRED_COLUMNS.get(self.data_kind, set())
        if not required:
            return []
        fields = {str(key) for row in rows for key in row}
        return sorted(required - fields)

    def _source_timestamp(self, rows: list[dict[str, Any]]) -> str:
        values = [
            str(row.get("source_timestamp") or row.get("source_published_at") or row.get("published_at") or "")
            for row in rows
        ]
        values = [value for value in values if value]
        return max(values) if values else ""

    def secret_values(self) -> tuple[str, ...]:
        return tuple(value for value in (self.token,) if value)
