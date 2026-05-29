from __future__ import annotations

import os
import re
from typing import Any

from ..api_clients import RateLimitedCacheClient
from ..config import load_project_env
from ..services.api_key_resolver import resolved_secret_value


def scrub_alpha_message(message: str) -> str:
    text = str(message or "")
    key = resolved_secret_value("SN_ALPHA_VANTAGE_KEY")
    if key:
        text = text.replace(key, "***")
    text = re.sub(r"(API key as )([A-Za-z0-9]+)", r"\1***", text, flags=re.IGNORECASE)
    text = re.sub(r"(apikey=)([^&\\s]+)", r"\1***", text, flags=re.IGNORECASE)
    return text


def classify_alpha_error(message: str) -> str:
    lower = str(message or "").lower()
    if not lower:
        return "request_failed"
    if "invalid" in lower or "forbidden" in lower or "401" in lower:
        return "key_invalid"
    if "frequency" in lower or "rate" in lower or "limit" in lower or "thank you for using alpha vantage" in lower:
        return "rate_limited"
    if "note" in lower or "information" in lower:
        return "rate_limited"
    if "timed out" in lower or "urlopen" in lower or "network" in lower:
        return "network_failed"
    return "request_failed"


class AlphaVantageProvider:
    """Safe Alpha Vantage adapter with a uniform project-level response shape."""

    name = "alphavantage"
    base_url = "https://www.alphavantage.co/query"

    def __init__(self, api_key: str | None = None, client: RateLimitedCacheClient | None = None) -> None:
        load_project_env()
        resolved = resolved_secret_value("SN_ALPHA_VANTAGE_KEY")
        self.api_key = (api_key if api_key is not None else resolved or os.getenv("SN_ALPHA_VANTAGE_KEY", "")).strip()
        self.client = client or RateLimitedCacheClient()

    def _disabled(self, message: str = "未配置 SN_ALPHA_VANTAGE_KEY") -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": False,
            "success": False,
            "from_cache": False,
            "message": scrub_alpha_message(message),
            "error_code": "key_missing",
            "data": None,
        }

    def _error(self, message: str) -> dict[str, Any]:
        return {
            "name": self.name,
            "enabled": bool(self.api_key),
            "success": False,
            "from_cache": False,
            "message": scrub_alpha_message(message),
            "error_code": classify_alpha_error(message),
            "data": None,
        }

    def query(self, function: str, **params: Any) -> dict[str, Any]:
        if not self.api_key:
            return self._disabled()
        query_params = {"function": function, **params, "apikey": self.api_key}
        try:
            response = self.client.fetch_json(
                source=self.name,
                url=self.base_url,
                params=query_params,
                ttl_seconds=1800,
                min_interval_seconds=60,
                daily_limit=20,
            )
        except Exception as exc:
            return self._error(str(exc))
        return {
            "name": self.name,
            "enabled": True,
            "success": True,
            "from_cache": bool(response.from_cache),
            "message": "Alpha Vantage 数据获取成功。",
            "error_code": "",
            "data": response.payload,
        }

    def fetch_exchange_rate(self, *, from_currency: str = "USD", to_currency: str = "CNY") -> dict[str, Any]:
        return self.query("CURRENCY_EXCHANGE_RATE", from_currency=from_currency, to_currency=to_currency)

    def fetch_fx_daily(
        self,
        *,
        from_symbol: str = "USD",
        to_symbol: str = "CNY",
        outputsize: str = "compact",
    ) -> dict[str, Any]:
        return self.query(
            "FX_DAILY",
            from_symbol=from_symbol,
            to_symbol=to_symbol,
            outputsize=outputsize,
        )

    def fetch_treasury_yield(self, *, interval: str = "daily", maturity: str = "10year") -> dict[str, Any]:
        return self.query("TREASURY_YIELD", interval=interval, maturity=maturity)

    def fetch_commodity_proxy(self, function: str = "COPPER", **params: Any) -> dict[str, Any]:
        return self.query(function, **params)


def fetch_alpha_vantage_status() -> dict[str, Any]:
    return AlphaVantageProvider().fetch_fx_daily()
