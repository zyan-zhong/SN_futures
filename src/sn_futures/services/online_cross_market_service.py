from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..data_providers.alphavantage_provider import AlphaVantageProvider, scrub_alpha_message
from ..runtime import get_user_output_dir
from .api_key_resolver import resolve_secret


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fundamentals_dir() -> Path:
    path = get_user_output_dir() / "fundamentals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _existing_cross_market_rows(path: Path) -> list[dict[str, Any]]:
    payload = _read_json(path)
    rows = payload.get("rows") if isinstance(payload, Mapping) else []
    return [row for row in rows if isinstance(row, dict) and not row.get("sample")]


def _preserve_existing_cross_market(data_path: Path, status: dict[str, Any]) -> dict[str, Any] | None:
    cached_rows = _existing_cross_market_rows(data_path)
    if not cached_rows:
        return None
    last_good_path = data_path.with_name("last_good_cross_market.json")
    if not last_good_path.exists():
        _write_json(last_good_path, {"generated_at": _now(), "sample": False, "rows": cached_rows, "from_cache": True})
    preserved = dict(status)
    preserved.update(
        {
            "success": False,
            "from_cache": True,
            "cache_used": True,
            "row_count": len(cached_rows),
            "last_good_path": str(last_good_path),
            "message_zh": "Alpha Vantage 当前刷新失败，已保留最近成功 cross-market 缓存；不会覆盖为 empty 文件。",
        }
    )
    return preserved


def _to_float(value: Any) -> float | None:
    try:
        number = float(str(value).replace(",", "").strip())
    except Exception:
        return None
    return number if pd.notna(number) else None


def parse_alpha_exchange_rate(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("Realtime Currency Exchange Rate")
    if not isinstance(raw, Mapping):
        return []
    value = _to_float(raw.get("5. Exchange Rate"))
    timestamp = str(raw.get("6. Last Refreshed") or _now())[:10]
    if value is None:
        return []
    return [{"trade_date": timestamp, "usd_cny": value, "source": "alpha_vantage_currency_exchange_rate", "status": "real"}]


def parse_alpha_fx_daily(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("Time Series FX (Daily)")
    if not isinstance(raw, Mapping):
        return []
    rows = []
    for date, values in raw.items():
        if isinstance(values, Mapping):
            value = _to_float(values.get("4. close"))
            if value is not None:
                rows.append({"trade_date": str(date)[:10], "usd_cny": value, "source": "alpha_vantage_fx_daily", "status": "real"})
    return sorted(rows, key=lambda row: row["trade_date"])


def parse_alpha_treasury_yield(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("data")
    if not isinstance(raw, list):
        return []
    rows = []
    for item in raw:
        if isinstance(item, Mapping):
            value = _to_float(item.get("value"))
            date = str(item.get("date") or "")[:10]
            if value is not None and date:
                rows.append({"trade_date": date, "us10y": value, "source": "alpha_vantage_treasury_yield", "status": "real"})
    return sorted(rows, key=lambda row: row["trade_date"])


def parse_alpha_commodity(payload: Mapping[str, Any], field_name: str = "copper_global_proxy") -> list[dict[str, Any]]:
    raw = payload.get("data")
    if not isinstance(raw, list):
        return []
    rows = []
    for item in raw:
        if isinstance(item, Mapping):
            value = _to_float(item.get("value"))
            date = str(item.get("date") or "")[:10]
            if value is not None and date:
                rows.append({"trade_date": date, field_name: value, "source": "alpha_vantage_commodity_proxy", "status": "real"})
    return sorted(rows, key=lambda row: row["trade_date"])


def _merge_rows(*series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for rows in series:
        for row in rows:
            date = str(row.get("trade_date") or "")
            if not date:
                continue
            by_date.setdefault(date, {"trade_date": date}).update(row)
    merged = [by_date[date] for date in sorted(by_date)]
    if not merged:
        return []
    frame = pd.DataFrame(merged)
    if "usd_cny" in frame.columns:
        frame["usd_cny"] = pd.to_numeric(frame["usd_cny"], errors="coerce")
        frame["usd_cny_return"] = frame["usd_cny"].pct_change(1, fill_method=None)
    if "us10y" in frame.columns:
        frame["us10y"] = pd.to_numeric(frame["us10y"], errors="coerce")
        frame["us10y_change"] = frame["us10y"].diff(1)
    if "copper_global_proxy" in frame.columns:
        frame["copper_global_proxy"] = pd.to_numeric(frame["copper_global_proxy"], errors="coerce")
        frame["copper_proxy_return"] = frame["copper_global_proxy"].pct_change(1, fill_method=None)
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def _classify_result(result: Mapping[str, Any]) -> str:
    if result.get("success"):
        return "success"
    code = str(result.get("error_code") or "").strip()
    if code:
        return code
    message = str(result.get("message") or result.get("message_zh") or "").lower()
    if "limit" in message or "frequency" in message or "note" in message:
        return "rate_limited"
    if "invalid" in message or "forbidden" in message or "401" in message:
        return "key_invalid"
    return "request_failed"


def _attempt(provider: str, result: Mapping[str, Any], row_count: int) -> dict[str, Any]:
    code = _classify_result(result)
    return {
        "provider": provider,
        "success": bool(result.get("success")) and code == "success",
        "from_cache": bool(result.get("from_cache")),
        "row_count": row_count,
        "error_code": "" if code == "success" else code,
        "message_zh": scrub_alpha_message(str(result.get("message") or result.get("message_zh") or "")),
    }


def fetch_usd_cny_exchange_rate(provider: AlphaVantageProvider) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not hasattr(provider, "fetch_exchange_rate"):
        result = {
            "success": False,
            "from_cache": False,
            "message_zh": "当前 Alpha Vantage provider 不支持 CURRENCY_EXCHANGE_RATE，已回退 FX_DAILY。",
        }
        attempt = _attempt("alphavantage_currency_exchange_rate", result, 0)
        attempt["error_code"] = "function_unavailable"
        return [], attempt
    result = provider.fetch_exchange_rate(from_currency="USD", to_currency="CNY")
    payload = result.get("data") if isinstance(result.get("data"), Mapping) else {}
    rows = parse_alpha_exchange_rate(payload)
    return rows, _attempt("alphavantage_currency_exchange_rate", result, len(rows))


def fetch_usd_cny_daily(provider: AlphaVantageProvider) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result = provider.fetch_fx_daily(from_symbol="USD", to_symbol="CNY", outputsize="compact")
    payload = result.get("data") if isinstance(result.get("data"), Mapping) else {}
    rows = parse_alpha_fx_daily(payload)
    return rows, _attempt("alphavantage_fx_daily", result, len(rows))


def fetch_us10y_daily(provider: AlphaVantageProvider) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result = provider.fetch_treasury_yield(interval="daily", maturity="10year")
    payload = result.get("data") if isinstance(result.get("data"), Mapping) else {}
    rows = parse_alpha_treasury_yield(payload)
    return rows, _attempt("alphavantage_treasury_yield", result, len(rows))


def fetch_copper_macro_proxy(provider: AlphaVantageProvider) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    result = provider.fetch_commodity_proxy("COPPER", interval="monthly")
    payload = result.get("data") if isinstance(result.get("data"), Mapping) else {}
    rows = parse_alpha_commodity(payload)
    return rows, _attempt("alphavantage_copper_proxy", result, len(rows))


def test_alpha_vantage_connection(provider: AlphaVantageProvider | None = None) -> dict[str, Any]:
    provider = provider or AlphaVantageProvider()
    if not provider.api_key:
        return {"configured": False, "success": False, "status": "key_missing", "message_zh": "未配置 Alpha Vantage key。"}
    rows, attempt = fetch_usd_cny_exchange_rate(provider)
    status = "success" if attempt.get("success") else str(attempt.get("error_code") or "failed")
    return {
        "configured": True,
        "success": bool(attempt.get("success")),
        "status": status,
        "row_count": len(rows),
        "message_zh": scrub_alpha_message(str(attempt.get("message_zh") or ("Alpha Vantage 验证成功。" if rows else "Alpha Vantage 验证未返回可用数据。"))),
    }


def refresh_online_cross_market_data(provider: AlphaVantageProvider | None = None, force: bool = False) -> dict[str, Any]:
    _ = force
    provider = provider or AlphaVantageProvider()
    out = _fundamentals_dir()
    data_path = out / "sn_cross_market.json"
    status_path = out / "fx_macro_provider_status.json"
    resolved = resolve_secret("SN_ALPHA_VANTAGE_KEY")
    if not provider.api_key:
        status = {
            "source_name": "online_cross_market",
            "status": "key_missing",
            "success": False,
            "configured": False,
            "key_source": str(resolved.get("source") or "none"),
            "row_count": 0,
            "message_zh": "未配置 Alpha Vantage key，无法自动获取 USD/CNY 和 US10Y。",
            "next_actions_zh": ["在设置页配置 Alpha Vantage key；客户不需要 CSV/Excel。"],
            "client_upload_required": False,
        }
        preserved = _preserve_existing_cross_market(data_path, status)
        if preserved is not None:
            _write_json(status_path, preserved)
            return sanitize_for_json({"status": "key_missing", "success": False, "output_files": [str(data_path), str(status_path)], **preserved})
        _write_json(data_path, {"generated_at": _now(), "sample": False, "rows": [], "message_zh": status["message_zh"]})
        _write_json(status_path, status)
        return sanitize_for_json({"status": "key_missing", "success": False, "output_files": [str(data_path), str(status_path)], **status})

    exchange_rows, exchange_attempt = fetch_usd_cny_exchange_rate(provider)
    fx_rows, fx_attempt = fetch_usd_cny_daily(provider)
    treasury_rows, treasury_attempt = fetch_us10y_daily(provider)
    copper_rows, copper_attempt = fetch_copper_macro_proxy(provider)
    attempts = [exchange_attempt, fx_attempt, treasury_attempt, copper_attempt]
    rows = _merge_rows(exchange_rows, fx_rows, treasury_rows, copper_rows)
    has_fx = any(row.get("usd_cny") is not None for row in rows)
    has_treasury = any(row.get("us10y") is not None for row in rows)
    success = bool(rows and (has_fx or has_treasury))
    blocking = [str(item.get("error_code")) for item in attempts if item.get("error_code")]
    alpha_status = "success" if success else (blocking[0] if blocking else "schema_mismatch")
    from_cache = False
    if not success:
        cached_rows = _existing_cross_market_rows(data_path)
        if cached_rows:
            rows = cached_rows
            has_fx = any(row.get("usd_cny") is not None for row in rows)
            has_treasury = any(row.get("us10y") is not None for row in rows)
            from_cache = bool(has_fx or has_treasury)
    status = {
        "source_name": "online_cross_market",
        "status": alpha_status,
        "success": success,
        "from_cache": from_cache,
        "configured": True,
        "key_source": str(resolved.get("source") or "none"),
        "row_count": len(rows),
        "last_attempt_time": _now(),
        "last_success_time": _now() if success else "",
        "message_zh": "USD/CNY、US10Y 和可选铜宏观代理已自动刷新。" if success else "Alpha Vantage 未写入可用跨市场数据，请查看 provider_attempts。",
        "next_actions_zh": ["如被限流，请稍后重试；Alpha Vantage 不提供沪锡库存/基差。"],
        "provider_attempts": attempts,
        "alpha_vantage_status": alpha_status,
        "rate_limit_message": "; ".join(str(item.get("message_zh") or "") for item in attempts if item.get("error_code") == "rate_limited"),
        "client_upload_required": False,
    }
    if not success:
        preserved = _preserve_existing_cross_market(data_path, status)
        if preserved is not None:
            _write_json(status_path, preserved)
            return sanitize_for_json({"status": status["status"], "success": False, "output_files": [str(data_path), str(status_path)], **preserved})
    _write_json(
        data_path,
        {
            "generated_at": _now(),
            "sample": False,
            "rows": rows,
            "message_zh": status["message_zh"],
            "provider_attempts": attempts,
            "alpha_vantage_status": alpha_status,
        },
    )
    if success:
        _write_json(
            out / "last_good_cross_market.json",
            {
                "generated_at": _now(),
                "sample": False,
                "rows": rows,
                "source": "alpha_vantage",
            },
        )
    _write_json(status_path, status)
    return sanitize_for_json({"status": status["status"], "success": success, "output_files": [str(data_path), str(status_path)], **status})
