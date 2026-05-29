from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping

import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..data_providers.alphavantage_provider import AlphaVantageProvider, scrub_alpha_message
from ..runtime import get_user_output_dir
from .alpha_rate_limit_policy import (
    classify_alpha_response,
    record_alpha_attempt,
    should_skip_due_to_cooldown,
)
from .api_key_resolver import resolve_secret
from .online_cross_market_service import (
    parse_alpha_commodity,
    parse_alpha_fx_daily,
    parse_alpha_treasury_yield,
)


EndpointFetcher = Callable[[AlphaVantageProvider], tuple[list[dict[str, Any]], Mapping[str, Any]]]


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fundamentals_dir() -> Path:
    path = get_user_output_dir() / "fundamentals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _rows_from_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, Mapping):
        rows = payload.get("rows") or payload.get("data") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [dict(row) for row in rows if isinstance(row, Mapping) and not row.get("sample")]


def _current_rows(data_path: Path) -> list[dict[str, Any]]:
    return _rows_from_payload(_read_json(data_path))


def _last_good_rows(out: Path) -> list[dict[str, Any]]:
    return _rows_from_payload(_read_json(out / "last_good_cross_market.json"))


def _merge_rows(*series: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_date: dict[str, dict[str, Any]] = {}
    for rows in series:
        for row in rows:
            date = str(row.get("trade_date") or "")[:10]
            if not date:
                continue
            clean = {k: v for k, v in row.items() if k != "lme_tin_close"}
            by_date.setdefault(date, {"trade_date": date}).update(clean)
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
        frame["copper_global_proxy_return"] = frame["copper_global_proxy"].pct_change(1, fill_method=None)
        frame["copper_proxy_return"] = frame["copper_global_proxy_return"]
    return frame.where(pd.notna(frame), None).to_dict(orient="records")


def _classify_provider_result(result: Mapping[str, Any], rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload = result.get("data") if isinstance(result.get("data"), Mapping) else result
    classification = classify_alpha_response(payload)
    status = str(result.get("error_code") or classification.get("status") or "request_failed")
    if result.get("success") is False:
        status = str(result.get("error_code") or classification.get("status") or "request_failed")
    elif classification.get("status") != "success":
        status = str(classification.get("status"))
    elif rows:
        status = "success"
    else:
        status = "schema_mismatch"
    return {
        "status": status,
        "success": status == "success",
        "cooldown_until": classification.get("cooldown_until") or "",
        "message_zh": classification.get("message_zh") or scrub_alpha_message(str(result.get("message") or "")),
    }


def _fetch_fx_daily(provider: AlphaVantageProvider) -> tuple[list[dict[str, Any]], Mapping[str, Any]]:
    result = provider.fetch_fx_daily(from_symbol="USD", to_symbol="CNY", outputsize="full")
    payload = result.get("data") if isinstance(result.get("data"), Mapping) else {}
    return parse_alpha_fx_daily(payload), result


def _fetch_treasury_yield(provider: AlphaVantageProvider) -> tuple[list[dict[str, Any]], Mapping[str, Any]]:
    result = provider.fetch_treasury_yield(interval="daily", maturity="10year")
    payload = result.get("data") if isinstance(result.get("data"), Mapping) else {}
    return parse_alpha_treasury_yield(payload), result


def _fetch_copper(provider: AlphaVantageProvider) -> tuple[list[dict[str, Any]], Mapping[str, Any]]:
    result = provider.fetch_commodity_proxy("COPPER", interval="monthly")
    payload = result.get("data") if isinstance(result.get("data"), Mapping) else {}
    return parse_alpha_commodity(payload), result


ENDPOINTS: tuple[dict[str, Any], ...] = (
    {"source": "fx_daily", "provider": "alphavantage_fx_daily", "fetcher": _fetch_fx_daily, "fields": ["usd_cny", "usd_cny_return"]},
    {"source": "treasury_yield_10y", "provider": "alphavantage_treasury_yield", "fetcher": _fetch_treasury_yield, "fields": ["us10y", "us10y_change"]},
    {"source": "copper_proxy", "provider": "alphavantage_copper_proxy", "fetcher": _fetch_copper, "fields": ["copper_global_proxy", "copper_global_proxy_return", "copper_proxy_return"]},
)


def _attempt_payload(endpoint: Mapping[str, Any], result: Mapping[str, Any] | None, rows: list[dict[str, Any]], status: str, message_zh: str = "") -> dict[str, Any]:
    return {
        "source": endpoint["source"],
        "provider": endpoint["provider"],
        "success": status == "success",
        "status": status,
        "error_code": "" if status == "success" else status,
        "row_count": len(rows),
        "fields": list(endpoint.get("fields") or []),
        "cooldown_until": str((result or {}).get("cooldown_until") or ""),
        "message_zh": scrub_alpha_message(message_zh or str((result or {}).get("message_zh") or (result or {}).get("message") or "")),
    }


def refresh_cross_market_backfill(
    provider: AlphaVantageProvider | None = None,
    *,
    force: bool = False,
    max_endpoints_per_run: int | None = None,
) -> dict[str, Any]:
    provider = provider or AlphaVantageProvider()
    out = _fundamentals_dir()
    data_path = out / "sn_cross_market.json"
    status_path = out / "fx_macro_provider_status.json"
    last_good_path = out / "last_good_cross_market.json"
    resolved = resolve_secret("SN_ALPHA_VANTAGE_KEY")

    if not getattr(provider, "api_key", ""):
        rows = _current_rows(data_path) or _last_good_rows(out)
        status = "key_missing"
        result = _finalize(
            out=out,
            data_path=data_path,
            status_path=status_path,
            last_good_path=last_good_path,
            rows=rows,
            attempts=[],
            status=status,
            success=False,
            from_cache=bool(rows),
            resolved_source=str(resolved.get("source") or "none"),
            message_zh="未配置 Alpha Vantage key，无法刷新 USD/CNY 与 US10Y；如有缓存则继续展示缓存。",
        )
        return result

    max_count = max_endpoints_per_run if max_endpoints_per_run is not None else (len(ENDPOINTS) if force else 1)
    attempts: list[dict[str, Any]] = []
    fetched_series: list[list[dict[str, Any]]] = []
    attempted_count = 0

    for endpoint in ENDPOINTS:
        source = str(endpoint["source"])
        if attempted_count >= max_count:
            attempts.append(_attempt_payload(endpoint, {"message_zh": "本轮已达到 Alpha Vantage 分批请求上限。"}, [], "deferred"))
            continue
        if not force and should_skip_due_to_cooldown(source):
            attempts.append(_attempt_payload(endpoint, {"message_zh": "Alpha Vantage endpoint 仍在冷却窗口内。"}, [], "cooldown"))
            continue
        rows, raw_result = endpoint["fetcher"](provider)
        classified = _classify_provider_result(raw_result, rows)
        status = str(classified["status"])
        attempt = _attempt_payload(endpoint, classified, rows, status, str(classified.get("message_zh") or ""))
        attempts.append(attempt)
        record_alpha_attempt(source, status, message_zh=attempt["message_zh"], row_count=len(rows))
        attempted_count += 1
        if status == "success":
            fetched_series.append(rows)

    current_rows = _current_rows(data_path)
    last_good_rows = _last_good_rows(out)
    if fetched_series:
        merged_rows = _merge_rows(current_rows, last_good_rows, *fetched_series)
    else:
        # On rate-limit/cooldown failures, preserve the visible cache exactly
        # as-is.  Derived return columns can be rebuilt during feature joins;
        # the refresh step must not mutate a known-good cache into a new shape.
        merged_rows = current_rows or last_good_rows
    success = bool(fetched_series and merged_rows)
    error_statuses = [str(item.get("status")) for item in attempts if item.get("status") not in {"success", "deferred", "cooldown"}]
    any_rate_limited = "rate_limited" in error_statuses or any(item.get("status") == "cooldown" for item in attempts)

    if success:
        final_status = "success"
        from_cache = False
        message = "Alpha Vantage cross-market 分批回填成功，已写入最近成功缓存。"
    elif merged_rows:
        final_status = "using_cache_rate_limited" if any_rate_limited else "using_cache"
        from_cache = True
        message = "Alpha Vantage 当前不可刷新，已使用最近成功 cross-market 缓存；不会覆盖为空文件。"
    else:
        final_status = error_statuses[0] if error_statuses else "schema_mismatch"
        from_cache = False
        message = "Alpha Vantage 未取得可用 cross-market 数据，且当前没有最近成功缓存。"

    return _finalize(
        out=out,
        data_path=data_path,
        status_path=status_path,
        last_good_path=last_good_path,
        rows=merged_rows,
        attempts=attempts,
        status=final_status,
        success=success,
        from_cache=from_cache,
        resolved_source=str(resolved.get("source") or "none"),
        message_zh=message,
        attempted_endpoint_count=attempted_count,
    )


def _finalize(
    *,
    out: Path,
    data_path: Path,
    status_path: Path,
    last_good_path: Path,
    rows: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
    status: str,
    success: bool,
    from_cache: bool,
    resolved_source: str,
    message_zh: str,
    attempted_endpoint_count: int = 0,
) -> dict[str, Any]:
    row_count = len(rows)
    data_payload = {
        "generated_at": _now(),
        "sample": False,
        "rows": rows,
        "from_cache": bool(from_cache),
        "status": status,
        "message_zh": message_zh,
        "provider_attempts": attempts,
        "alpha_vantage_status": status,
    }
    existing_visible_rows = _current_rows(data_path)
    if rows and (success or not existing_visible_rows):
        _write_json(data_path, data_payload)
    elif not data_path.exists():
        _write_json(data_path, data_payload)

    if success and rows:
        _write_json(
            last_good_path,
            {
                "generated_at": _now(),
                "sample": False,
                "rows": rows,
                "source": "alpha_vantage",
                "status": "success",
            },
        )
    elif from_cache and rows and not existing_visible_rows:
        _write_json(data_path, data_payload)

    cooldowns = [str(item.get("cooldown_until") or "") for item in attempts if item.get("cooldown_until")]
    status_payload = {
        "source_name": "online_cross_market",
        "status": status,
        "success": bool(success),
        "from_cache": bool(from_cache),
        "configured": resolved_source != "none",
        "key_source": resolved_source,
        "row_count": row_count,
        "last_attempt_time": _now(),
        "last_success_time": _now() if success else "",
        "cooldown_until": cooldowns[0] if cooldowns else "",
        "provider_attempts": attempts,
        "attempted_endpoint_count": int(attempted_endpoint_count),
        "alpha_vantage_status": status,
        "client_upload_required": False,
        "message_zh": message_zh,
        "next_actions_zh": [
            "如显示 rate_limited，请等待冷却窗口或次日刷新。",
            "如已有缓存，系统会继续使用最近成功 cross-market 缓存。",
            "Alpha Vantage 不提供沪锡主行情、LME 锡、库存或基差，系统不会伪造这些字段。",
        ],
        "customer_prediction_generated": False,
        "active_model_written": False,
        "baseline_used": False,
    }
    _write_json(status_path, status_payload)
    return sanitize_for_json(
        {
            "status": status,
            "success": bool(success),
            "from_cache": bool(from_cache),
            "row_count": row_count,
            "output_files": [str(data_path), str(status_path), str(last_good_path)],
            **status_payload,
        }
    )
