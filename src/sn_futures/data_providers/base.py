from __future__ import annotations

import hashlib
import json
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text, sanitize_url


PROVIDER_SCHEMA_VERSION = "provider-result-v1"


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _content_hash(payload: Any) -> str:
    encoded = json.dumps(sanitize_for_json(sanitize_mapping(payload)), ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


@dataclass(frozen=True)
class ProviderStatus:
    provider_id: str
    data_kind: str
    success: bool
    status_code: str
    error_code: str
    row_count: int
    normalized_row_count: int
    fetched_at: str
    source_timestamp: str
    as_of: str
    from_cache: bool
    stale: bool
    rate_limited: bool
    schema_version: str
    manifest: dict[str, Any]
    sanitized_error: str

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_json(sanitize_mapping(asdict(self)))


@dataclass(frozen=True)
class ProviderResult:
    provider_id: str
    data_kind: str
    success: bool
    status_code: str
    error_code: str
    rows: list[dict[str, Any]]
    normalized_rows: list[dict[str, Any]]
    fetched_at: str
    source_timestamp: str
    as_of: str
    from_cache: bool
    stale: bool
    rate_limited: bool
    schema_version: str
    manifest: dict[str, Any]
    sanitized_error: str

    def to_status(self) -> ProviderStatus:
        return ProviderStatus(
            provider_id=self.provider_id,
            data_kind=self.data_kind,
            success=self.success,
            status_code=self.status_code,
            error_code=self.error_code,
            row_count=len(self.rows),
            normalized_row_count=len(self.normalized_rows),
            fetched_at=self.fetched_at,
            source_timestamp=self.source_timestamp,
            as_of=self.as_of,
            from_cache=self.from_cache,
            stale=self.stale,
            rate_limited=self.rate_limited,
            schema_version=self.schema_version,
            manifest=dict(self.manifest),
            sanitized_error=self.sanitized_error,
        )

    def to_dict(self) -> dict[str, Any]:
        return sanitize_for_json(sanitize_mapping(asdict(self)))


class BaseProvider(ABC):
    provider_id: str
    data_kind: str
    source_url: str = ""
    raw_filename: str = "raw.json"
    normalized_filename: str = "normalized.json"

    def fetch(self, *, persist: bool = False, output_dir: Path | None = None) -> ProviderResult:
        try:
            raw_response = self.fetch_raw()
        except Exception as exc:
            return self._error_result(
                error_code=self.classify_error(str(exc)),
                sanitized_error=sanitize_text(str(exc), self.secret_values()),
                fetched_at=_now(),
            )

        fetched_at = str(getattr(raw_response, "fetched_at", "") or _now())
        from_cache = bool(getattr(raw_response, "from_cache", False))
        source_url = sanitize_url(str(getattr(raw_response, "url", "") or self.source_url), self.secret_values())
        raw_payload = sanitize_mapping(getattr(raw_response, "payload", None), self.secret_values())

        try:
            rows = self.extract_rows(raw_response)
            normalized_rows = self.normalize(rows)
            validation = self.validate(raw_response, rows, normalized_rows)
        except Exception as exc:
            return self._error_result(
                error_code="malformed_response",
                sanitized_error=sanitize_text(str(exc), self.secret_values()),
                fetched_at=fetched_at,
                from_cache=from_cache,
                source_url=source_url,
            )

        if not validation.get("success", False):
            return self._error_result(
                error_code=str(validation.get("error_code") or "validation_failed"),
                sanitized_error=str(validation.get("sanitized_error") or ""),
                fetched_at=fetched_at,
                from_cache=from_cache,
                source_url=source_url,
                status_code=str(validation.get("status_code") or ""),
                rows=rows,
            )

        source_timestamp = self.source_timestamp(normalized_rows)
        manifest = self.build_manifest(
            rows=rows,
            normalized_rows=normalized_rows,
            fetched_at=fetched_at,
            source_timestamp=source_timestamp,
            from_cache=from_cache,
            stale=False,
            rate_limited=False,
            source_url_sanitized=source_url,
            raw_payload=raw_payload,
        )
        result = ProviderResult(
            provider_id=self.provider_id,
            data_kind=self.data_kind,
            success=True,
            status_code=str(validation.get("status_code") or ""),
            error_code="",
            rows=[dict(row) for row in rows],
            normalized_rows=[dict(row) for row in normalized_rows],
            fetched_at=fetched_at,
            source_timestamp=source_timestamp,
            as_of=source_timestamp or fetched_at,
            from_cache=from_cache,
            stale=False,
            rate_limited=False,
            schema_version=PROVIDER_SCHEMA_VERSION,
            manifest=manifest,
            sanitized_error="",
        )
        if persist:
            root = output_dir or get_user_output_dir()
            self.write_raw(raw_payload, root)
            self.write_normalized(result.normalized_rows, root)
        return result

    @abstractmethod
    def fetch_raw(self) -> Any:
        raise NotImplementedError

    @abstractmethod
    def extract_rows(self, raw_response: Any) -> list[dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def normalize(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise NotImplementedError

    def validate(self, raw_response: Any, rows: list[dict[str, Any]], normalized_rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not isinstance(rows, list) or not isinstance(normalized_rows, list):
            return {"success": False, "error_code": "malformed_response", "sanitized_error": "malformed provider response"}
        return {"success": True, "status_code": ""}

    def write_raw(self, payload: Any, output_dir: Path | None = None) -> Path:
        root = output_dir or get_user_output_dir()
        path = root / "providers" / self.provider_id / "raw" / self.raw_filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sanitize_for_json(sanitize_mapping(payload, self.secret_values())), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def write_normalized(self, rows: list[dict[str, Any]], output_dir: Path | None = None) -> Path:
        root = output_dir or get_user_output_dir()
        path = root / "providers" / self.provider_id / "normalized" / self.normalized_filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(sanitize_for_json(sanitize_mapping(rows, self.secret_values())), ensure_ascii=False, indent=2), encoding="utf-8")
        return path

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
        return sanitize_for_json(
            sanitize_mapping(
                {
                    "provider_id": self.provider_id,
                    "data_kind": self.data_kind,
                    "schema_version": PROVIDER_SCHEMA_VERSION,
                    "fetched_at": fetched_at,
                    "source_timestamp": source_timestamp,
                    "as_of": source_timestamp or fetched_at,
                    "row_count": len(rows),
                    "normalized_row_count": len(normalized_rows),
                    "from_cache": from_cache,
                    "stale": stale,
                    "rate_limited": rate_limited,
                    "cache_status": "cache" if from_cache else "remote",
                    "stale_status": "stale" if stale else "fresh",
                    "source_url_sanitized": source_url_sanitized,
                    "content_hash": _content_hash({"rows": rows, "normalized_rows": normalized_rows, "raw": raw_payload}),
                    "sample_data_used": False,
                    "baseline_used": False,
                    "blocking_reasons": [],
                },
                self.secret_values(),
            )
        )

    def source_timestamp(self, normalized_rows: list[dict[str, Any]]) -> str:
        values = [str(row.get("source_timestamp") or row.get("published_at") or row.get("quote_time") or "") for row in normalized_rows]
        values = [value for value in values if value]
        return max(values) if values else ""

    def secret_values(self) -> Iterable[str]:
        return ()

    def classify_error(self, message: str) -> str:
        lower = str(message or "").lower()
        if "rate" in lower or "limit" in lower or "429" in lower:
            return "rate_limited"
        if "401" in lower or "403" in lower or "invalid" in lower or "key" in lower:
            return "auth_failed"
        if "malformed" in lower or "parse" in lower:
            return "malformed_response"
        return "request_failed"

    def _error_result(
        self,
        *,
        error_code: str,
        sanitized_error: str,
        fetched_at: str,
        from_cache: bool = False,
        source_url: str = "",
        status_code: str = "",
        rows: list[dict[str, Any]] | None = None,
    ) -> ProviderResult:
        rate_limited = error_code == "rate_limited"
        manifest = self.build_manifest(
            rows=rows or [],
            normalized_rows=[],
            fetched_at=fetched_at,
            source_timestamp="",
            from_cache=from_cache,
            stale=False,
            rate_limited=rate_limited,
            source_url_sanitized=sanitize_url(source_url or self.source_url, self.secret_values()),
            raw_payload={},
        )
        manifest["blocking_reasons"] = [sanitize_text(sanitized_error, self.secret_values())] if sanitized_error else [error_code]
        return ProviderResult(
            provider_id=self.provider_id,
            data_kind=self.data_kind,
            success=False,
            status_code=str(status_code or ""),
            error_code=str(error_code or "request_failed"),
            rows=[dict(row) for row in (rows or [])],
            normalized_rows=[],
            fetched_at=fetched_at,
            source_timestamp="",
            as_of="",
            from_cache=from_cache,
            stale=False,
            rate_limited=rate_limited,
            schema_version=PROVIDER_SCHEMA_VERSION,
            manifest=manifest,
            sanitized_error=sanitize_text(sanitized_error, self.secret_values()),
        )
