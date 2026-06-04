from __future__ import annotations

import json
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping

from ..api.json_utils import sanitize_for_json
from ..contracts import resolve_target_contract
from ..runtime import get_user_output_dir
from ..user_data import initialize_user_data_dir
from .data_quality_service import compute_data_quality_score
from .freshness_policy import classify_freshness


MIN_CHART_HISTORY_ROWS = 20
MIN_ANALYSIS_HISTORY_ROWS = 60
GOOD_HISTORY_ROWS = 120
OPTIONAL_MARKET_PROVIDERS = (
    "akshare_history",
    "akshare_news",
    "shfe_public",
    "shfe_direct",
)
OPTIONAL_MARKET_PREFIXES = (
    "akshare_futures_",
    "akshare_news_",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _outputs_dir() -> Path:
    initialize_user_data_dir()
    path = get_user_output_dir()
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


def _as_float(value: Any) -> float | None:
    if value in (None, ""):
        return None
    try:
        parsed = float(str(value).replace(",", "").strip())
    except Exception:
        return None
    if parsed != parsed or parsed in {float("inf"), float("-inf")}:
        return None
    return parsed


def _duration(started_perf: float) -> float:
    return round(time.perf_counter() - started_perf, 3)


def is_optional_market_provider(provider_name: str, chain: str = "") -> bool:
    provider = str(provider_name or "").strip().lower()
    chain_name = str(chain or "").strip().lower()
    if provider in OPTIONAL_MARKET_PROVIDERS:
        return True
    if any(provider.startswith(prefix) for prefix in OPTIONAL_MARKET_PREFIXES):
        return True
    return provider.startswith("akshare_") and chain_name in {"history", "news", "auxiliary"}


def sanitize_provider_error_message(value: Any) -> str:
    text = str(value or "")
    if not text:
        return ""

    def _hide_windows_path(match: re.Match[str]) -> str:
        filename = Path(match.group(1)).name
        return f"[local-path-hidden]\\{filename}"

    def _hide_posix_path(match: re.Match[str]) -> str:
        filename = Path(match.group(1)).name
        return f"[local-path-hidden]/{filename}"

    text = re.sub(
        r"[A-Za-z]:\\.*?([^\\/:*?\"<>|\r\n]+\.(?:dll|pyd|so|dylib|py|json|txt|log|csv))",
        _hide_windows_path,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(
        r"/(?:[^/\r\n]+/)+([^/\r\n]+\.(?:dll|pyd|so|dylib|py|json|txt|log|csv))",
        _hide_posix_path,
        text,
        flags=re.IGNORECASE,
    )
    text = re.sub(r"[A-Za-z]:\\[^\r\n;，。]+", "[local-path-hidden]", text)
    return text


def _provider_attempt(
    provider_name: str,
    *,
    chain: str,
    started_at: str,
    started_perf: float,
    attempted: bool = True,
    success: bool = False,
    from_cache: bool = False,
    stale: bool = False,
    status_code: str = "",
    error_type: str = "",
    error_message_zh: str = "",
    rows: int = 0,
    latest_price: Any = None,
    latest_time: str = "",
    symbol_used: str = "",
    request_params_sanitized: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    optional = is_optional_market_provider(provider_name, chain)
    resolved_status = status_code or ("success" if success else "failed")
    if optional and not success and resolved_status in {"failed", "error", "request_failed"}:
        resolved_status = "optional_failed"
    sanitized_error = sanitize_provider_error_message(error_message_zh)
    blocking = bool(attempted and not success and not from_cache and not optional)
    return {
        "provider_name": provider_name,
        "chain": chain,
        "attempted": attempted,
        "success": success,
        "from_cache": from_cache,
        "stale": stale,
        "started_at": started_at,
        "finished_at": _now(),
        "duration_seconds": _duration(started_perf),
        "status_code": resolved_status,
        "optional": optional,
        "blocking": blocking,
        "severity": "success" if success else "optional_failed" if optional else "fatal",
        "error_type": error_type,
        "error_message_zh": sanitized_error,
        "rows": rows,
        "row_count": rows,
        "latest_price": latest_price,
        "latest_time": latest_time,
        "symbol_used": symbol_used,
        "request_params_sanitized": dict(request_params_sanitized or {}),
    }


def normalize_sn_contract_symbol(symbol: str | None) -> str:
    text = (symbol or "").strip()
    if not text:
        return "nf_SN0"
    if text.startswith("nf_"):
        return "nf_" + text[3:].upper()
    upper = text.upper().replace("SHFE.", "").replace("SHFE/", "").replace("SHFE:", "")
    if upper in {"SN", "SN0", "SN00"}:
        return "nf_SN0"
    if upper.startswith("SN"):
        return f"nf_{upper}"
    return text


def _ak_symbol(symbol: str | None) -> str:
    normalized = normalize_sn_contract_symbol(symbol)
    if normalized.startswith("nf_"):
        return normalized.replace("nf_", "").upper()
    return normalized.upper()


def _unique(values: Iterable[str]) -> list[str]:
    rows: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if text and text not in rows:
            rows.append(text)
    return rows


def _sina_symbol_candidates() -> list[str]:
    rows: list[str] = []
    try:
        contract = resolve_target_contract()
        meta = contract if isinstance(contract, Mapping) else getattr(contract, "__dict__", {})
        if isinstance(meta, Mapping):
            rows.extend(
                [
                    normalize_sn_contract_symbol(str(meta.get("target_contract_symbol", "") or "")),
                    normalize_sn_contract_symbol(str(meta.get("active_contract_symbol", "") or "")),
                    normalize_sn_contract_symbol(str(meta.get("continuous_symbol", "") or "")),
                ]
            )
            candidates = meta.get("candidates", [])
            if isinstance(candidates, list):
                rows.extend(normalize_sn_contract_symbol(str(item.get("sina_symbol", "") or "")) for item in candidates if isinstance(item, Mapping))
    except Exception:
        pass
    rows.extend(["nf_SN0", "nf_sn0", "SN0", "sn0"])
    return _unique(rows)


def _history_symbol_candidates() -> list[str]:
    return ["SN0", "sn0", "SN", "sn"]


def _extract_price(row: Mapping[str, Any]) -> float | None:
    aliases = (
        "current_price",
        "最新价",
        "price",
        "close",
        "last_price",
        "sell_price",
        "卖价",
        "buy_price",
        "买价",
        "收盘",
        "收盘价",
        "latest",
    )
    for key in aliases:
        value = _as_float(row.get(key))
        if value is not None and value > 0:
            return value
    return None


def _normalize_history_rows(rows: Iterable[Mapping[str, Any]], *, source: str, symbol: str) -> list[dict[str, Any]]:
    normalized: dict[str, dict[str, Any]] = {}
    for row in rows:
        timestamp = str(row.get("date") or row.get("日期") or row.get("time") or row.get("时间") or "").strip()
        close = _as_float(row.get("close") or row.get("收盘") or row.get("收盘价"))
        if close is None or close <= 0:
            continue
        item = {
            "time": timestamp,
            "date": timestamp,
            "open": _as_float(row.get("open") or row.get("开盘")) or close,
            "high": _as_float(row.get("high") or row.get("最高")) or close,
            "low": _as_float(row.get("low") or row.get("最低")) or close,
            "close": close,
            "volume": _as_float(row.get("volume") or row.get("成交量")),
            "open_interest": _as_float(row.get("open_interest") or row.get("持仓量") or row.get("持仓")),
            "source": source,
            "symbol": symbol,
        }
        key = timestamp or f"{source}-{symbol}-{len(normalized)}"
        normalized[key] = item
    return sorted(normalized.values(), key=lambda item: str(item.get("time") or item.get("date") or ""))


def _history_from_payload(payload: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(payload, Mapping):
        return []
    for key in ("points", "history"):
        rows = payload.get(key)
        if isinstance(rows, list):
            return [dict(row) for row in rows if isinstance(row, Mapping)]
    return []


def _cache_age(payload: Mapping[str, Any] | None) -> str:
    if not isinstance(payload, Mapping):
        return ""
    ts = str(payload.get("generated_at") or payload.get("quote_time") or "")
    if not ts:
        return ""
    try:
        age = datetime.now() - datetime.fromisoformat(ts.replace("Z", "+00:00").replace("+08:00", ""))
        return str(age).split(".")[0]
    except Exception:
        return ""


def _read_cache_file(name: str) -> dict[str, Any] | None:
    payload = _read_json(_outputs_dir() / name)
    return dict(payload) if isinstance(payload, Mapping) else None


def load_last_good_realtime_quote() -> dict[str, Any] | None:
    return _read_cache_file("last_good_realtime_quote.json")


def load_last_good_market_history() -> dict[str, Any] | None:
    return _read_cache_file("last_good_market_history.json")


def load_last_good_market_cache() -> dict[str, Any] | None:
    realtime = load_last_good_realtime_quote()
    history = load_last_good_market_history()
    legacy = _read_cache_file("last_good_market.json")
    if not realtime and not history:
        return legacy
    return {
        "generated_at": _now(),
        "realtime": realtime,
        "history": history,
        "legacy": legacy,
        "latest_price": realtime.get("latest_price") if isinstance(realtime, Mapping) else None,
        "quote_time": realtime.get("quote_time") if isinstance(realtime, Mapping) else "",
        "history_rows": len(_history_from_payload(history)),
    }


def save_market_cache(payload: Mapping[str, Any]) -> None:
    _write_json(_outputs_dir() / "last_good_market.json", dict(payload))


def validate_market_payload(payload: Mapping[str, Any] | None) -> tuple[bool, str]:
    if not isinstance(payload, Mapping):
        return False, "行情返回不是有效对象。"
    latest_price = _as_float(payload.get("latest_price"))
    history = _history_from_payload(payload)
    if latest_price is None and not history:
        return False, "缺少最新价和历史行情。"
    if latest_price is not None and latest_price <= 0:
        return False, "最新价不合理。"
    return True, "行情 payload 可用。"


def refresh_realtime_quote() -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    quote: dict[str, Any] | None = None

    try:
        from ..api_clients import SinaFinanceClient
        from ..market_data_hub import _normalize_sina_quote

        client = SinaFinanceClient()
        for symbol in _sina_symbol_candidates():
            started_at = _now()
            started_perf = time.perf_counter()
            try:
                response = client.fetch_quotes([symbol])
                rows = client.parse_quotes(str(response.payload or ""))
                candidates = [_normalize_sina_quote(row) for row in rows]
                valid = [row for row in candidates if _as_float(row.get("latest")) and float(row.get("latest") or 0) > 0]
                if not valid:
                    attempts.append(
                        _provider_attempt(
                            "sina_realtime",
                            chain="realtime",
                            started_at=started_at,
                            started_perf=started_perf,
                            symbol_used=symbol,
                            rows=len(rows),
                            error_type="empty_quote",
                            error_message_zh="Sina 未返回可用沪锡实时行情。",
                            request_params_sanitized={"symbol": symbol},
                        )
                    )
                    continue
                row = valid[0]
                latest_price = _as_float(row.get("latest"))
                quote = {
                    "source": "sina_realtime",
                    "provider": "sina_realtime",
                    "active_contract": str(row.get("symbol") or symbol),
                    "latest_quote": row,
                    "latest_price": latest_price,
                    "quote_time": str(row.get("quote_time") or response.fetched_at or _now()),
                    "symbol_used": symbol,
                    "from_cache": bool(response.from_cache),
                }
                attempts.append(
                    _provider_attempt(
                        "sina_realtime",
                        chain="realtime",
                        started_at=started_at,
                        started_perf=started_perf,
                        success=True,
                        from_cache=bool(response.from_cache),
                        rows=len(valid),
                        latest_price=latest_price,
                        latest_time=str(quote["quote_time"]),
                        symbol_used=symbol,
                        request_params_sanitized={"symbol": symbol},
                    )
                )
                break
            except Exception as exc:
                attempts.append(
                    _provider_attempt(
                        "sina_realtime",
                        chain="realtime",
                        started_at=started_at,
                        started_perf=started_perf,
                        symbol_used=symbol,
                        error_type=type(exc).__name__,
                        error_message_zh=f"Sina 实时行情请求失败：{exc}",
                        request_params_sanitized={"symbol": symbol},
                    )
                )
    except Exception as exc:
        attempts.append(
            _provider_attempt(
                "sina_realtime",
                chain="realtime",
                started_at=_now(),
                started_perf=time.perf_counter(),
                error_type=type(exc).__name__,
                error_message_zh=f"Sina 实时行情客户端不可用：{exc}",
            )
        )

    if quote is None:
        quote, ak_attempts = _refresh_akshare_realtime()
        attempts.extend(ak_attempts)

    return {
        "success": quote is not None,
        "quote": quote,
        "attempts": attempts,
        "message_zh": "实时行情刷新成功。" if quote else "实时行情源均未返回可用价格。",
    }


def _call_akshare(fn: Callable[..., Any], variants: list[dict[str, Any]]) -> Any:
    last_exc: Exception | None = None
    for params in variants:
        try:
            return fn(**params)
        except TypeError as exc:
            last_exc = exc
            continue
    if last_exc:
        raise last_exc
    raise TypeError("AKShare 调用参数不兼容")


def _refresh_akshare_realtime() -> tuple[dict[str, Any] | None, list[dict[str, Any]]]:
    attempts: list[dict[str, Any]] = []
    try:
        import akshare as ak  # type: ignore
    except Exception as exc:
        return None, [
            _provider_attempt(
                "akshare_realtime",
                chain="realtime",
                started_at=_now(),
                started_perf=time.perf_counter(),
                error_type=type(exc).__name__,
                error_message_zh=f"AKShare 未安装或不可用：{exc}",
            )
        ]

    fn = getattr(ak, "futures_zh_spot", None)
    if fn is None:
        return None, [
            _provider_attempt(
                "akshare_realtime",
                chain="realtime",
                started_at=_now(),
                started_perf=time.perf_counter(),
                error_type="missing_function",
                error_message_zh="AKShare 缺少 futures_zh_spot 接口。",
            )
        ]

    for symbol in ("SN0", "sn0"):
        for adjust in ("0", "1"):
            started_at = _now()
            started_perf = time.perf_counter()
            params = {"symbol": symbol, "market": "CF", "adjust": adjust}
            try:
                df = _call_akshare(
                    fn,
                    [
                        params,
                        {"symbol": symbol, "market": "CF"},
                        {"symbol": symbol},
                    ],
                )
                rows = df.to_dict("records") if hasattr(df, "to_dict") else []
                valid_rows = [row for row in rows if isinstance(row, Mapping)]
                if not valid_rows:
                    raise ValueError("AKShare 返回空实时行情。")
                row = dict(valid_rows[0])
                latest_price = _extract_price(row)
                if latest_price is None:
                    raise ValueError("AKShare 实时行情缺少可识别价格字段。")
                quote_time = str(row.get("time") or row.get("时间") or row.get("datetime") or row.get("quote_time") or _now())
                attempts.append(
                    _provider_attempt(
                        "akshare_realtime",
                        chain="realtime",
                        started_at=started_at,
                        started_perf=started_perf,
                        success=True,
                        rows=len(valid_rows),
                        latest_price=latest_price,
                        latest_time=quote_time,
                        symbol_used=symbol,
                        request_params_sanitized=params,
                    )
                )
                return {
                    "source": "akshare_realtime",
                    "provider": "akshare_realtime",
                    "active_contract": symbol.upper(),
                    "latest_quote": row,
                    "latest_price": latest_price,
                    "quote_time": quote_time,
                    "symbol_used": symbol,
                    "from_cache": False,
                }, attempts
            except Exception as exc:
                attempts.append(
                    _provider_attempt(
                        "akshare_realtime",
                        chain="realtime",
                        started_at=started_at,
                        started_perf=started_perf,
                        symbol_used=symbol,
                        error_type=type(exc).__name__,
                        error_message_zh=f"AKShare 实时行情不可用：{exc}",
                        request_params_sanitized=params,
                    )
                )
    return None, attempts


def refresh_market_history() -> dict[str, Any]:
    attempts: list[dict[str, Any]] = []
    try:
        import akshare as ak  # type: ignore
    except Exception as exc:
        return {
            "success": False,
            "history": [],
            "attempts": [
                _provider_attempt(
                    "akshare_history",
                    chain="history",
                    started_at=_now(),
                    started_perf=time.perf_counter(),
                    error_type=type(exc).__name__,
                    error_message_zh=f"AKShare 未安装或不可用：{exc}",
                )
            ],
            "message_zh": "历史行情源不可用。",
        }

    candidates = [
        ("akshare_futures_zh_daily_sina", getattr(ak, "futures_zh_daily_sina", None)),
        ("akshare_futures_main_sina", getattr(ak, "futures_main_sina", None)),
    ]
    for provider_name, fn in candidates:
        if fn is None:
            attempts.append(
                _provider_attempt(
                    provider_name,
                    chain="history",
                    started_at=_now(),
                    started_perf=time.perf_counter(),
                    error_type="missing_function",
                    error_message_zh=f"AKShare 缺少 {provider_name} 接口。",
                )
            )
            continue
        for symbol in _history_symbol_candidates():
            started_at = _now()
            started_perf = time.perf_counter()
            params = {"symbol": symbol}
            try:
                df = _call_akshare(fn, [{"symbol": symbol}, {"symbol": symbol.upper()}, {}])
                rows = df.to_dict("records") if hasattr(df, "to_dict") else []
                history = _normalize_history_rows([row for row in rows if isinstance(row, Mapping)], source=provider_name, symbol=symbol)
                if len(history) < MIN_CHART_HISTORY_ROWS:
                    raise ValueError(f"历史行情不足 {MIN_CHART_HISTORY_ROWS} 条，当前 {len(history)} 条。")
                attempts.append(
                    _provider_attempt(
                        provider_name,
                        chain="history",
                        started_at=started_at,
                        started_perf=started_perf,
                        success=True,
                        rows=len(history),
                        latest_price=history[-1].get("close"),
                        latest_time=str(history[-1].get("time") or ""),
                        symbol_used=symbol,
                        request_params_sanitized=params,
                    )
                )
                return {
                    "success": True,
                    "history": history,
                    "attempts": attempts,
                    "source": provider_name,
                    "symbol": symbol,
                    "row_count": len(history),
                    "message_zh": "历史行情刷新成功。",
                }
            except Exception as exc:
                attempts.append(
                    _provider_attempt(
                        provider_name,
                        chain="history",
                        started_at=started_at,
                        started_perf=started_perf,
                        symbol_used=symbol,
                        rows=0,
                        error_type=type(exc).__name__,
                        error_message_zh=f"{provider_name} 历史行情不可用：{exc}",
                        request_params_sanitized=params,
                    )
                )
    return {"success": False, "history": [], "attempts": attempts, "message_zh": "历史行情源均未返回足够数据。"}


def refresh_shfe_public_aux() -> dict[str, Any]:
    started_at = _now()
    started_perf = time.perf_counter()
    status = _provider_attempt(
        "shfe_public",
        chain="auxiliary",
        started_at=started_at,
        started_perf=started_perf,
        attempted=True,
        success=False,
        status_code="auxiliary_unavailable",
        error_type="auxiliary_unavailable",
        error_message_zh="SHFE public 当前仅作为日线/库存/仓单辅助源；本版本未将其作为沪锡主行情源。",
        symbol_used="SN",
    )
    payload = {
        "success": False,
        "status": "auxiliary_unavailable",
        "attempts": [status],
        "data": {},
        "message_zh": "SHFE public 辅助源未启用可靠数据读取，不影响主行情刷新。",
    }
    out = _outputs_dir()
    _write_json(out / "shfe_public_status.json", payload)
    _write_json(
        out / "shfe_auxiliary_data.json",
        {"generated_at": _now(), "data": {}, "message_zh": payload["message_zh"]},
    )
    return payload


def _cache_status(realtime_cache: Mapping[str, Any] | None, history_cache: Mapping[str, Any] | None) -> dict[str, Any]:
    return {
        "realtime_cache_exists": isinstance(realtime_cache, Mapping),
        "history_cache_exists": isinstance(history_cache, Mapping),
        "realtime_cache_age": _cache_age(realtime_cache),
        "history_cache_age": _cache_age(history_cache),
        "realtime_rows": 1 if isinstance(realtime_cache, Mapping) and _as_float(realtime_cache.get("latest_price")) else 0,
        "history_rows": len(_history_from_payload(history_cache)),
    }


def merge_market_data(
    realtime_result: Mapping[str, Any],
    history_result: Mapping[str, Any],
    shfe_aux_result: Mapping[str, Any] | None = None,
    cache_result: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    realtime = realtime_result.get("quote") if isinstance(realtime_result.get("quote"), Mapping) else None
    history = history_result.get("history") if isinstance(history_result.get("history"), list) else []
    history_attempts = [item for item in history_result.get("attempts", []) if isinstance(item, Mapping)]
    shfe_attempts = [item for item in (shfe_aux_result or {}).get("attempts", []) if isinstance(item, Mapping)]
    optional_source_failures = [
        dict(item)
        for item in history_attempts + shfe_attempts
        if str(item.get("status_code") or item.get("status") or "") == "optional_failed"
    ]
    if cache_result is None:
        realtime_cache = load_last_good_realtime_quote()
        history_cache = load_last_good_market_history()
    else:
        realtime_cache = cache_result.get("realtime") if isinstance(cache_result, Mapping) and isinstance(cache_result.get("realtime"), Mapping) else None
        history_cache = cache_result.get("history") if isinstance(cache_result, Mapping) and isinstance(cache_result.get("history"), Mapping) else None

    realtime_is_real = isinstance(realtime, Mapping) and _as_float(realtime.get("latest_price")) is not None
    history_is_real = len(history) >= MIN_CHART_HISTORY_ROWS
    used_realtime_cache = False
    used_history_cache = False

    if not realtime_is_real and isinstance(realtime_cache, Mapping) and _as_float(realtime_cache.get("latest_price")) is not None:
        realtime = dict(realtime_cache)
        realtime["from_cache"] = True
        used_realtime_cache = True

    if not history_is_real and isinstance(history_cache, Mapping):
        cached_history = _history_from_payload(history_cache)
        if cached_history:
            history = cached_history
            used_history_cache = True

    history_rows = len(history)
    latest_price = _as_float(realtime.get("latest_price")) if isinstance(realtime, Mapping) else None
    quote_time = str(realtime.get("quote_time") or "") if isinstance(realtime, Mapping) else ""
    active_contract = str(realtime.get("active_contract") or "SN0") if isinstance(realtime, Mapping) else "SN0"

    if latest_price is None and history_rows:
        latest_price = _as_float(history[-1].get("close"))
        quote_time = str(history[-1].get("time") or history[-1].get("date") or "")
        active_contract = str(history[-1].get("symbol") or active_contract)

    if (used_realtime_cache or used_history_cache) and not (realtime_is_real or history_is_real):
        final_status = "cache_only"
        message_zh = "仅使用最近成功缓存，不能当作新行情。"
    elif realtime_is_real and history_rows >= MIN_ANALYSIS_HISTORY_ROWS:
        final_status = "full_success"
        message_zh = "实时行情和历史行情均可用。"
    elif (not realtime_is_real) and history_rows >= MIN_ANALYSIS_HISTORY_ROWS:
        final_status = "history_only_success"
        message_zh = "历史行情可用，实时价暂缺。"
    elif realtime_is_real and history_rows < MIN_CHART_HISTORY_ROWS:
        final_status = "quote_only_partial"
        message_zh = "实时价可用，但历史行情不足，不能预测/回测。"
    elif history_rows >= MIN_CHART_HISTORY_ROWS:
        final_status = "history_only_success" if history_rows >= MIN_ANALYSIS_HISTORY_ROWS else "cache_only" if used_history_cache else "history_only_success"
        message_zh = "历史行情可用于图表展示，但不足以生成预测/回测。" if history_rows < MIN_ANALYSIS_HISTORY_ROWS else "历史行情可用，实时价暂缺。"
    else:
        final_status = "failed"
        message_zh = "无可用实时行情、历史行情或最近成功缓存。"

    blocking_reasons: list[str] = []
    next_actions_zh: list[str] = []
    if not realtime_is_real:
        blocking_reasons.append("实时行情不可用。")
        next_actions_zh.append("查看 Sina/AKShare 实时行情 provider 诊断。")
    if history_rows < MIN_CHART_HISTORY_ROWS:
        blocking_reasons.append("历史行情不足，无法绘制有效图表。")
        next_actions_zh.append("检查 AKShare 历史行情接口或网络。")
    elif history_rows < MIN_ANALYSIS_HISTORY_ROWS:
        blocking_reasons.append("历史行情少于 60 条，不能生成预测/回测。")
        next_actions_zh.append("继续刷新历史行情或检查合约符号。")
    if final_status == "cache_only":
        blocking_reasons.append("当前仅有缓存，不能作为新行情。")
        next_actions_zh.append("等待实时/历史 provider 恢复后重新刷新。")
    if final_status == "failed":
        next_actions_zh.append("检查网络、AKShare 安装、Sina 访问和本地日志。")
    if realtime_is_real and optional_source_failures:
        blocking_reasons = []
    market_status = "failed" if final_status == "failed" else "usable"
    warnings_zh = [
        f"AKShare 可选源失败，不影响主行情：{item.get('error_message_zh') or item.get('message_zh') or item.get('provider_name')}"
        for item in optional_source_failures
    ]

    return {
        "generated_at": _now(),
        "final_status": final_status,
        "market_status": market_status,
        "market_usable": market_status == "usable",
        "success": final_status != "failed",
        "message_zh": message_zh,
        "latest_price": latest_price,
        "quote_time": quote_time,
        "active_contract": active_contract,
        "latest_quote": dict(realtime or {}),
        "history": history,
        "history_rows": history_rows,
        "realtime_is_real": realtime_is_real,
        "history_is_real": history_is_real,
        "from_cache": bool(used_realtime_cache or used_history_cache),
        "realtime_from_cache": used_realtime_cache,
        "history_from_cache": used_history_cache,
        "stale": bool(used_realtime_cache or used_history_cache),
        "source": str((realtime or {}).get("source") or history_result.get("source") or "market_provider"),
        "history_source": str(history_result.get("source") or ("last_good_market_history" if used_history_cache else "")),
        "realtime_status": realtime_result,
        "history_status": history_result,
        "shfe_aux_status": shfe_aux_result or {},
        "cache_status": _cache_status(realtime_cache, history_cache),
        "blocking_reasons": blocking_reasons,
        "next_actions_zh": _unique(next_actions_zh),
        "optional_source_failures": optional_source_failures,
        "warnings_zh": warnings_zh,
    }


def merge_market_payloads(payloads: list[Mapping[str, Any]]) -> dict[str, Any] | None:
    valid = [dict(payload) for payload in payloads if validate_market_payload(payload)[0]]
    if not valid:
        return None
    realtime_result = {"quote": next((payload for payload in valid if payload.get("latest_price")), None), "attempts": []}
    history_payload = next((payload for payload in valid if _history_from_payload(payload)), {})
    history_result = {"history": _history_from_payload(history_payload), "attempts": [], "source": history_payload.get("source", "")}
    merged = merge_market_data(realtime_result, history_result, {}, load_last_good_market_cache())
    return merged if merged.get("success") else None


def _status_for_output(result: Mapping[str, Any], chain_key: str) -> dict[str, Any]:
    attempts = result.get("attempts") if isinstance(result.get("attempts"), list) else []
    last_success = next((attempt for attempt in reversed(attempts) if isinstance(attempt, Mapping) and attempt.get("success")), None)
    return {
        "chain": chain_key,
        "success": bool(result.get("success")),
        "attempts": attempts,
        "message_zh": result.get("message_zh", ""),
        "last_success": dict(last_success) if isinstance(last_success, Mapping) else None,
    }


def refresh_sn_market_data(force: bool = False) -> dict[str, Any]:
    _ = force
    out = _outputs_dir()
    realtime_result = refresh_realtime_quote()
    history_result = refresh_market_history()
    shfe_aux_result = refresh_shfe_public_aux()
    cache_result = load_last_good_market_cache() or {}
    merged = merge_market_data(realtime_result, history_result, shfe_aux_result, cache_result)

    latest_price = _as_float(merged.get("latest_price"))
    history = _history_from_payload(merged)
    quality = compute_data_quality_score(
        {
            "latest_price": latest_price,
            "quote_time": merged.get("quote_time"),
            "from_cache": bool(merged.get("from_cache")),
            "history_rows": len(history),
            "news_configured": False,
            "news_count": 0,
            "event_count": 0,
            "report_count": 0,
            "prediction_count": 0,
            "model_status": "待验证",
        }
    )
    freshness = classify_freshness(
        "local_market_cache" if merged.get("from_cache") else "realtime_market",
        merged.get("quote_time"),
        merged.get("trading_session"),
        enabled=True,
        success=bool(merged.get("success")),
        from_cache=bool(merged.get("from_cache")),
    )

    realtime_attempts = realtime_result.get("attempts") if isinstance(realtime_result.get("attempts"), list) else []
    history_attempts = history_result.get("attempts") if isinstance(history_result.get("attempts"), list) else []
    shfe_attempts = shfe_aux_result.get("attempts") if isinstance(shfe_aux_result.get("attempts"), list) else []
    provider_status = {
        "updated_at": _now(),
        "realtime_attempts": realtime_attempts,
        "history_attempts": history_attempts,
        "shfe_attempts": shfe_attempts,
        "providers": realtime_attempts + history_attempts + shfe_attempts,
        "cache_status": merged.get("cache_status", {}),
        "final_status": merged.get("final_status"),
        "blocking_reasons": merged.get("blocking_reasons", []),
        "next_actions_zh": merged.get("next_actions_zh", []),
        "message_zh": merged.get("message_zh", ""),
    }
    snapshot = {
        "generated_at": _now(),
        "latest_quote": merged.get("latest_quote", {}),
        "active_contract": merged.get("active_contract") or "SN0",
        "latest_price": latest_price,
        "quote_time": merged.get("quote_time") or "",
        "realtime_status": _status_for_output(realtime_result, "realtime"),
        "history_status": _status_for_output(history_result, "history"),
        "shfe_aux_status": _status_for_output(shfe_aux_result, "auxiliary"),
        "source_status": realtime_attempts + history_attempts + shfe_attempts,
        "provider_chain_status": provider_status,
        "data_quality_score": quality["score"],
        "data_quality": quality,
        "freshness": freshness,
        "from_cache": bool(merged.get("from_cache")),
        "realtime_from_cache": bool(merged.get("realtime_from_cache")),
        "history_from_cache": bool(merged.get("history_from_cache")),
        "stale": bool(freshness.get("stale")) or bool(merged.get("stale")),
        "source": merged.get("source") or "market_provider",
        "final_status": merged.get("final_status"),
        "history_row_count": len(history),
        "blocking_reasons": merged.get("blocking_reasons", []),
        "next_actions_zh": merged.get("next_actions_zh", []),
        "message_zh": merged.get("message_zh"),
    }
    history_payload = {
        "symbol": "SN",
        "contract": snapshot["active_contract"],
        "points": history,
        "history": history,
        "row_count": len(history),
        "source": merged.get("history_source") or merged.get("source") or "market_provider",
        "from_cache": bool(merged.get("history_from_cache")),
        "stale": bool(merged.get("history_from_cache")),
        "generated_at": _now(),
        "data_quality_score": quality["score"],
        "message_zh": "历史行情可用。" if history else "历史行情不可用。",
    }
    watermark = {
        "generated_at": _now(),
        "latest_price": latest_price,
        "quote_time": snapshot["quote_time"],
        "source": snapshot["source"],
        "quality_score": quality["score"],
        "data_quality_score": quality["score"],
        "data_quality_label": quality["label"],
        "data_quality_components": quality["components"],
        "data_quality_blocking_reasons": quality["blocking_reasons"],
        "data_quality_degradation_reasons": quality["degradation_reasons"],
        "data_quality_next_actions_zh": quality["next_actions_zh"],
        "from_cache": snapshot["from_cache"],
        "realtime_from_cache": snapshot["realtime_from_cache"],
        "history_from_cache": snapshot["history_from_cache"],
        "stale": snapshot["stale"],
        "freshness": freshness,
        "active_contract": snapshot["active_contract"],
        "final_status": snapshot["final_status"],
        "history_rows": len(history),
        "blocking_reasons": snapshot["blocking_reasons"],
        "next_actions_zh": snapshot["next_actions_zh"],
    }

    _write_json(out / "sn_live_snapshot.json", snapshot)
    _write_json(out / "sn_market_history.json", history_payload)
    _write_json(out / "data_watermark.json", watermark)
    _write_json(out / "market_provider_status.json", provider_status)
    if snapshot["realtime_status"]["success"]:
        _write_json(out / "last_good_realtime_quote.json", {**snapshot["latest_quote"], "latest_price": latest_price, "quote_time": snapshot["quote_time"], "generated_at": _now(), "active_contract": snapshot["active_contract"], "source": snapshot["source"]})
    if len(history) >= MIN_CHART_HISTORY_ROWS and not history_payload["from_cache"]:
        _write_json(out / "last_good_market_history.json", history_payload)
    if merged.get("success"):
        save_market_cache(snapshot)

    return {
        "success": bool(merged.get("success")),
        "final_status": merged.get("final_status"),
        "from_cache": snapshot["from_cache"],
        "stale": snapshot["stale"],
        "message_zh": snapshot["message_zh"],
        "latest_price": latest_price,
        "history_rows": len(history),
        "data_quality": quality,
        "provider_chain_status": realtime_attempts + history_attempts + shfe_attempts,
        "market_provider_status": provider_status,
        "output_files": [
            str(out / "sn_live_snapshot.json"),
            str(out / "sn_market_history.json"),
            str(out / "data_watermark.json"),
            str(out / "market_provider_status.json"),
            str(out / "last_good_realtime_quote.json"),
            str(out / "last_good_market_history.json"),
            str(out / "shfe_public_status.json"),
            str(out / "shfe_auxiliary_data.json"),
        ],
    }


def get_market_provider_chain_status() -> dict[str, Any]:
    payload = _read_json(_outputs_dir() / "market_provider_status.json")
    if isinstance(payload, Mapping):
        return sanitize_for_json(payload)
    return {"realtime_attempts": [], "history_attempts": [], "shfe_attempts": [], "message_zh": "尚未运行行情刷新。", "updated_at": _now()}
