from __future__ import annotations

from typing import Any

from ..api_clients import RateLimitedCacheClient, SinaFinanceClient
from .base import BaseProvider


def _safe_float(values: list[str], index: int) -> float | None:
    try:
        raw = str(values[index]).replace(",", "").strip()
        if raw == "":
            return None
        return float(raw)
    except Exception:
        return None


def _normalize_sina_quote_row(row: dict[str, Any]) -> dict[str, Any]:
    fields = row.get("raw_fields", [])
    if not isinstance(fields, list):
        fields = []
    symbol = str(row.get("symbol") or "")
    if symbol.startswith("nf_"):
        open_price = _safe_float(fields, 2)
        high = _safe_float(fields, 3)
        low = _safe_float(fields, 4)
        latest = _safe_float(fields, 8) or _safe_float(fields, 6) or _safe_float(fields, 3)
        prev_close = _safe_float(fields, 10) or _safe_float(fields, 27) or _safe_float(fields, 2)
        volume = _safe_float(fields, 13)
        open_interest = _safe_float(fields, 14)
    else:
        open_price = _safe_float(fields, 1)
        prev_close = _safe_float(fields, 2)
        latest = _safe_float(fields, 3)
        high = _safe_float(fields, 4)
        low = _safe_float(fields, 5)
        volume = _safe_float(fields, 8)
        open_interest = _safe_float(fields, 9)
    return {
        "provider_id": "sina_realtime_quote",
        "data_kind": "realtime_quote",
        "symbol": symbol,
        "name": str(row.get("name") or ""),
        "open": open_price,
        "prev_close": prev_close,
        "latest": latest,
        "high": high,
        "low": low,
        "volume": volume,
        "open_interest": open_interest,
        "quote_time": "",
        "source_timestamp": "",
        "sample_data_used": False,
        "baseline_used": False,
    }


class SinaRealtimeQuoteProvider(BaseProvider):
    provider_id = "sina_realtime_quote"
    data_kind = "realtime_quote"
    source_url = SinaFinanceClient.BASE_URL
    raw_filename = "sina_realtime_quote_raw.json"
    normalized_filename = "sina_realtime_quote_normalized.json"

    def __init__(self, *, symbols: list[str] | None = None, client: RateLimitedCacheClient | None = None) -> None:
        self.symbols = symbols or ["nf_SN0"]
        self.client = client or RateLimitedCacheClient()

    def fetch_raw(self) -> Any:
        return SinaFinanceClient(client=self.client).fetch_quotes(self.symbols)

    def extract_rows(self, raw_response: Any) -> list[dict[str, Any]]:
        payload = getattr(raw_response, "payload", "")
        if not isinstance(payload, str):
            raise ValueError("malformed Sina response: payload is not text")
        return SinaFinanceClient.parse_quotes(payload)

    def normalize(self, rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [_normalize_sina_quote_row(row) for row in rows]

    def validate(self, raw_response: Any, rows: list[dict[str, Any]], normalized_rows: list[dict[str, Any]]) -> dict[str, Any]:
        if not rows or not normalized_rows:
            return {
                "success": False,
                "error_code": "malformed_response",
                "sanitized_error": "malformed Sina realtime quote response: no quote rows parsed",
            }
        if not any(row.get("latest") for row in normalized_rows):
            return {
                "success": False,
                "error_code": "malformed_response",
                "sanitized_error": "malformed Sina realtime quote response: latest price missing",
            }
        return {"success": True, "status_code": ""}
