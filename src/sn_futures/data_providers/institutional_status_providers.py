from __future__ import annotations

from dataclasses import replace
from datetime import datetime
from typing import Any, Callable, Iterable, Mapping, Protocol

try:
    import pandas as pd
except Exception:  # pragma: no cover - pandas is available in the project env
    pd = None  # type: ignore[assignment]

from ..api.json_utils import sanitize_for_json
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text
from .base import BaseProvider, ProviderResult


class RowsClient(Protocol):
    def fetch_rows(self) -> Any:
        ...


class _MissingClient:
    pass


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _as_rows(payload: Any) -> list[dict[str, Any]]:
    if payload is None:
        return []
    if pd is not None and isinstance(payload, pd.DataFrame):  # type: ignore[arg-type]
        return [dict(row) for row in payload.to_dict("records")]
    if isinstance(payload, list):
        if any(not isinstance(row, Mapping) for row in payload):
            raise ValueError("malformed provider response: rows must be objects")
        return [dict(row) for row in payload if isinstance(row, Mapping)]
    if isinstance(payload, Mapping):
        for key in ("rows", "data", "items", "events", "articles"):
            value = payload.get(key)
            if isinstance(value, list):
                if any(not isinstance(row, Mapping) for row in value):
                    raise ValueError("malformed provider response: rows must be objects")
                return [dict(row) for row in value if isinstance(row, Mapping)]
    raise ValueError("malformed provider response")


def _source_status(provider_id: str, *, success: bool, row_count: int, error_code: str = "", message: str = "") -> dict[str, Any]:
    return sanitize_for_json(
        sanitize_mapping(
            {
                "source_id": provider_id,
                "provider_id": provider_id,
                "success": success,
                "row_count": row_count,
                "error_code": error_code,
                "error_message_sanitized": message,
            }
        )
    )


class _InstitutionalContractProvider(BaseProvider):
    provider_id = "institutional_contract"
    data_kind = "provider_status"
    required_fields: tuple[str, ...] = ()
    source_url = ""

    def __init__(
        self,
        *,
        client: Any | None = None,
        token: str = "",
        fetch_method: str = "fetch_rows",
        module_loader: Callable[[], Any] | None = None,
    ) -> None:
        self.client = client if client is not None else _MissingClient()
        self.token = str(token or "")
        self.fetch_method = fetch_method
        self.module_loader = module_loader

    def fetch_raw(self) -> Any:
        if self.token_required and not self.token:
            raise RuntimeError("token_missing")
        if self.module_loader is not None:
            try:
                self.module_loader()
            except ImportError as exc:
                raise RuntimeError(f"import_missing:{exc}") from exc
        fn = getattr(self.client, self.fetch_method, None)
        if not callable(fn):
            raise RuntimeError(f"api_changed: missing {self.fetch_method}")
        return type(
            "ServiceProviderResponse",
            (),
            {
                "payload": fn(),
                "fetched_at": _now(),
                "from_cache": False,
                "url": self.source_url,
            },
        )()

    @property
    def token_required(self) -> bool:
        return False

    def extract_rows(self, raw_response: Any) -> list[dict[str, Any]]:
        return _as_rows(getattr(raw_response, "payload", None))

    def normalize(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized: list[dict[str, Any]] = []
        for row in rows:
            item = sanitize_for_json(sanitize_mapping(dict(row), self.secret_values()))
            item["provider_id"] = self.provider_id
            item["data_kind"] = self.data_kind
            normalized.append(item)
        return normalized

    def validate(self, raw_response: Any, rows: list[dict[str, Any]], normalized_rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows:
            return {"success": False, "error_code": "no_rows", "sanitized_error": "provider returned no rows"}
        missing_fields: set[str] = set()
        for row in normalized_rows:
            missing = [field for field in self.required_fields if not str(row.get(field) or "").strip()]
            missing_fields.update(missing)
        if missing_fields:
            return {
                "success": False,
                "error_code": "missing_required_columns",
                "sanitized_error": "missing required columns: " + ", ".join(sorted(missing_fields)),
            }
        return {"success": True, "status_code": "success"}

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
        success = bool(normalized_rows)
        manifest.update(
            {
                "source_statuses": [_source_status(self.provider_id, success=success, row_count=len(normalized_rows))],
                "allowed_for_display": success,
                "allowed_for_feature_store": False,
                "allowed_for_training": False,
                "allowed_for_prediction": False,
                "allowed_for_backtest": False,
                "feature_store_written": False,
                "training_invoked": False,
                "backtest_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
                "source_published_at_coverage": self._source_published_at_coverage(normalized_rows),
            }
        )
        return sanitize_for_json(sanitize_mapping(manifest, self.secret_values()))

    def _error_result(self, **kwargs: Any) -> ProviderResult:
        result = super()._error_result(**kwargs)
        manifest = dict(result.manifest)
        manifest.update(
            {
                "source_statuses": [
                    _source_status(
                        self.provider_id,
                        success=False,
                        row_count=0,
                        error_code=result.error_code,
                        message=result.sanitized_error,
                    )
                ],
                "allowed_for_display": False,
                "allowed_for_feature_store": False,
                "allowed_for_training": False,
                "allowed_for_prediction": False,
                "allowed_for_backtest": False,
                "feature_store_written": False,
                "training_invoked": False,
                "backtest_invoked": False,
                "active_updated": False,
                "customer_prediction_generated": False,
                "source_published_at_coverage": 0.0,
            }
        )
        return replace(result, manifest=sanitize_for_json(sanitize_mapping(manifest, self.secret_values())))

    def source_timestamp(self, normalized_rows: list[dict[str, Any]]) -> str:
        values = [
            str(
                row.get("source_published_at")
                or row.get("published_at")
                or row.get("trade_date")
                or row.get("source_timestamp")
                or ""
            )
            for row in normalized_rows
        ]
        values = [value for value in values if value]
        return max(values) if values else ""

    def secret_values(self) -> Iterable[str]:
        return (self.token,) if self.token else ()

    def classify_error(self, message: str) -> str:
        lower = str(message or "").lower()
        if "token_missing" in lower:
            return "token_missing"
        if "import_missing" in lower or "no module named" in lower:
            return "import_missing"
        if "api_changed" in lower or "missing fetch_rows" in lower:
            return "api_changed"
        if "rate" in lower or "limit" in lower or "429" in lower:
            return "rate_limited"
        if "malformed" in lower or "parse" in lower:
            return "malformed_response"
        return super().classify_error(message)

    def _source_published_at_coverage(self, normalized_rows: list[dict[str, Any]]) -> float:
        if not normalized_rows:
            return 0.0
        with_published = [row for row in normalized_rows if str(row.get("source_published_at") or row.get("published_at") or "").strip()]
        return round(len(with_published) / len(normalized_rows), 4)


class TushareFuturesContractProvider(_InstitutionalContractProvider):
    provider_id = "tushare_futures"
    data_kind = "futures_fundamentals"
    required_fields = ("ts_code", "trade_date")
    source_url = "https://api.tushare.pro"

    @property
    def token_required(self) -> bool:
        return True


class ShfePublicContractProvider(_InstitutionalContractProvider):
    provider_id = "shfe_public"
    data_kind = "exchange_public"
    required_fields = ("symbol", "trade_date")
    source_url = "https://www.shfe.com.cn"


class PublicPolicyRssContractProvider(_InstitutionalContractProvider):
    provider_id = "public_policy_rss"
    data_kind = "policy"
    required_fields = ("title", "url", "source_published_at")

    def _source_published_at_coverage(self, normalized_rows: list[dict[str, Any]]) -> float:
        if not normalized_rows:
            return 0.0
        with_published = [row for row in normalized_rows if str(row.get("source_published_at") or "").strip()]
        return round(len(with_published) / len(normalized_rows), 4)
