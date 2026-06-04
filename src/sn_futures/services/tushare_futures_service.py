from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text
from .api_key_resolver import resolve_secret
from .tushare_param_probe_service import build_tushare_param_probe_report, classify_tushare_error, probe_tushare_interface


TIN_PRODUCT_NAMES = ("锡", "沪锡", "SN", "sn")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fundamentals_dir() -> Path:
    path = get_user_output_dir() / "fundamentals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(sanitize_mapping(dict(payload))), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _safe_error_message(exc: Exception) -> str:
    resolved = resolve_secret("SN_TUSHARE_TOKEN")
    return sanitize_text(str(exc), extra_secrets=[str(resolved.get("value") or "")])


def _exception_status(exc: Exception) -> str:
    return classify_tushare_error(exc)
    text = str(exc).lower()
    if "tushare_package_missing" in text:
        return "tushare_package_missing"
    if any(token in text for token in ("权限", "permission", "forbidden", "unauthorized", "没有访问", "无权限")):
        return "permission_denied"
    if any(token in text for token in ("quota", "积分", "权限不足", "insufficient")):
        return "quota_insufficient"
    if any(token in text for token in ("limit", "频率", "rate", "每分钟", "访问次数")):
        return "rate_limited"
    if any(token in text for token in ("token", "invalid", "认证", "auth")):
        return "key_invalid"
    if any(token in text for token in ("timeout", "connection", "network", "网络")):
        return "network_failed"
    return "request_failed"


def _fail_result(result: dict[str, Any], exc: Exception, api_name: str) -> dict[str, Any]:
    status = _exception_status(exc)
    result.update(
        {
            "attempted": True,
            "success": False,
            "status": status,
            "row_count": 0,
            "rows": [],
            "error_message_zh": f"Tushare {api_name} request failed: {_safe_error_message(exc)}",
            "message_zh": f"Tushare {api_name} request failed with status={status}; no fake data was written.",
            "next_actions_zh": [
                "If status is permission_denied/quota_insufficient, check Tushare Pro permissions or quota.",
                "If status is rate_limited, wait for cooldown before retrying.",
            ],
        }
    )
    return sanitize_for_json(result)


def _numeric(value: Any) -> float | int | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    number = float(parsed)
    return int(number) if number.is_integer() else number


def _date(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    parsed = pd.to_datetime(text, errors="coerce")
    if pd.isna(parsed):
        return text
    return pd.Timestamp(parsed).strftime("%Y-%m-%d")


def _tushare_date(value: Any) -> str:
    parsed = _date(value)
    return parsed.replace("-", "") if parsed else ""


def _market_history_date_bounds() -> tuple[str, str]:
    payload = _read_json(get_user_output_dir() / "sn_market_history.json")
    if isinstance(payload, Mapping):
        rows = payload.get("history") or payload.get("rows") or payload.get("points") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    dates: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        value = row.get("trade_date") or row.get("date") or row.get("time")
        parsed = _tushare_date(value)
        if parsed:
            dates.append(parsed)
    if not dates:
        return "", ""
    return min(dates), max(dates)


def normalize_tushare_futures_symbol(symbol: Any) -> str:
    text = str(symbol or "").strip().upper()
    if not text:
        return ""
    base = text.split(".", 1)[0]
    if not base.startswith("SN"):
        return ""
    return base


def _is_tin_row(row: Mapping[str, Any]) -> bool:
    for key in ("ts_code", "symbol", "contract", "fut_code"):
        if normalize_tushare_futures_symbol(row.get(key)):
            return True
    haystack = " ".join(str(row.get(key, "") or "") for key in ("product", "name", "variety", "exchange", "fut_name"))
    if "铜" in haystack or "CU" in haystack.upper():
        return False
    return any(token in haystack for token in TIN_PRODUCT_NAMES)


def _frame_from_call(client: Any, method: str, **params: Any) -> pd.DataFrame:
    fn = getattr(client, method)
    payload = fn(**params)
    if isinstance(payload, pd.DataFrame):
        return payload.copy()
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    return pd.DataFrame()


def _frame_from_market_date_range(client: Any, method: str, chunk_days: int = 720, **params: Any) -> pd.DataFrame:
    start_text, end_text = _market_history_date_bounds()
    if not start_text or not end_text:
        return _frame_from_call(client, method, **params)
    start = pd.Timestamp(start_text)
    end = pd.Timestamp(end_text)
    frames: list[pd.DataFrame] = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + pd.Timedelta(days=max(30, int(chunk_days))), end)
        frame = _frame_from_call(
            client,
            method,
            **params,
            start_date=cursor.strftime("%Y%m%d"),
            end_date=chunk_end.strftime("%Y%m%d"),
        )
        if not frame.empty:
            frames.append(frame)
        cursor = chunk_end + pd.Timedelta(days=1)
    if not frames:
        return pd.DataFrame()
    combined = pd.concat(frames, ignore_index=True)
    return combined.drop_duplicates()


def _market_history_dates(limit: int = 30) -> list[str]:
    payload = _read_json(get_user_output_dir() / "sn_market_history.json")
    if isinstance(payload, Mapping):
        rows = payload.get("history") or payload.get("rows") or payload.get("points") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    dates: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        parsed = _tushare_date(row.get("trade_date") or row.get("date") or row.get("time"))
        if parsed:
            dates.append(parsed)
    return sorted(set(dates))[-max(1, int(limit)) :]


def _is_aux_tin_row(row: Mapping[str, Any]) -> bool:
    haystack = " ".join(str(row.get(key, "") or "") for key in ("ts_code", "symbol", "contract", "product", "variety", "name", "warehouse")).upper()
    if "CU" in haystack or "铜" in haystack:
        return False
    return "SN" in haystack or "锡" in haystack or bool(normalize_tushare_futures_symbol(row.get("ts_code") or row.get("symbol") or row.get("contract")))


def _probe_or_fail(result: dict[str, Any], api: Any, api_name: str) -> tuple[dict[str, Any] | None, pd.DataFrame]:
    outcome = probe_tushare_interface(api, api_name)
    probe = dict(outcome.report)
    result["params_sanitized"] = probe.get("params_sanitized", {})
    result["selected_params"] = probe.get("selected_params", {})
    result["probe_status"] = probe.get("status")
    if not probe.get("success"):
        result.update(
            {
                "attempted": True,
                "success": False,
                "status": str(probe.get("status") or "request_failed"),
                "row_count": 0,
                "rows": [],
                "fields": list(probe.get("columns") or []),
                "error_message_zh": str(probe.get("error_message_zh") or ""),
                "message_zh": f"Tushare {api_name} probe failed with status={probe.get('status')}; no fake data was written.",
            }
        )
        return sanitize_for_json(result), pd.DataFrame()
    return None, outcome.frame


def _expand_selected_frame(api: Any, api_name: str, selected_params: Mapping[str, Any], seed_frame: pd.DataFrame) -> pd.DataFrame:
    selected = {key: value for key, value in dict(selected_params or {}).items() if value not in (None, "")}
    if not selected:
        return seed_frame.copy()
    if "trade_date" not in selected:
        try:
            frame = _frame_from_call(api, api_name, **selected)
            return frame if not frame.empty else seed_frame.copy()
        except Exception:
            return seed_frame.copy()
    frames: list[pd.DataFrame] = []
    dates = _market_history_dates() or [str(selected.get("trade_date"))]
    for trade_date in dates:
        params = dict(selected)
        params["trade_date"] = trade_date
        params.pop("start_date", None)
        params.pop("end_date", None)
        try:
            frame = _frame_from_call(api, api_name, **params)
        except Exception:
            continue
        if not frame.empty:
            frames.append(frame)
    if not frames:
        return seed_frame.copy()
    return pd.concat(frames, ignore_index=True).drop_duplicates()


class _HttpTushareClient:
    def __init__(self, token: str) -> None:
        self.token = token

    def _call(self, api_name: str, **params: Any) -> pd.DataFrame:
        import requests

        response = requests.post(
            "https://api.tushare.pro",
            json={"api_name": api_name, "token": self.token, "params": params, "fields": ""},
            timeout=30,
        )
        response.raise_for_status()
        payload = response.json()
        code = int(payload.get("code") or 0)
        if code != 0:
            raise RuntimeError(str(payload.get("msg") or f"tushare_code_{code}"))
        data = payload.get("data") if isinstance(payload.get("data"), Mapping) else {}
        fields = data.get("fields") if isinstance(data, Mapping) else []
        items = data.get("items") if isinstance(data, Mapping) else []
        if not isinstance(fields, list) or not isinstance(items, list):
            return pd.DataFrame()
        return pd.DataFrame(items, columns=[str(field) for field in fields])

    def fut_basic(self, **params: Any) -> pd.DataFrame:
        return self._call("fut_basic", **params)

    def trade_cal(self, **params: Any) -> pd.DataFrame:
        return self._call("trade_cal", **params)

    def fut_daily(self, **params: Any) -> pd.DataFrame:
        return self._call("fut_daily", **params)

    def fut_wsr(self, **params: Any) -> pd.DataFrame:
        return self._call("fut_wsr", **params)

    def fut_settle(self, **params: Any) -> pd.DataFrame:
        return self._call("fut_settle", **params)

    def fut_holding(self, **params: Any) -> pd.DataFrame:
        return self._call("fut_holding", **params)


def _get_client(token: str | None = None) -> Any:
    token_text = str(token or "").strip()
    try:
        import tushare as ts  # type: ignore
    except Exception as exc:  # pragma: no cover - exercised through status tests without dependency
        if token_text:
            return _HttpTushareClient(token_text)
        raise RuntimeError("tushare_package_missing") from exc
    return ts.pro_api(token_text)


def _token_status() -> dict[str, Any]:
    resolved = resolve_secret("SN_TUSHARE_TOKEN")
    if not resolved.get("configured"):
        return {
            "configured": False,
            "source": "none",
            "masked": "",
            "status": "token_missing",
            "message_zh": "未配置 Tushare token；可在设置页填写 SN_TUSHARE_TOKEN，或通过环境变量提供。",
            "next_actions_zh": ["在设置页填写 Tushare token。", "Tushare 仅用于期货基础数据，不用于实盘交易。"],
        }
    return {
        "configured": True,
        "source": str(resolved.get("source") or "none"),
        "masked": str(resolved.get("masked") or ""),
        "status": "configured",
        "message_zh": "Tushare token 已配置，等待接口验证。",
        "next_actions_zh": ["点击刷新 Tushare 基础数据。"],
    }


def _base_result(provider_name: str, function_name: str, params: Mapping[str, Any] | None = None) -> dict[str, Any]:
    token = _token_status()
    return {
        "provider_name": provider_name,
        "function_name": function_name,
        "params_sanitized": dict(params or {}),
        "attempted": False,
        "success": False,
        "status": token["status"],
        "row_count": 0,
        "date_start": "",
        "date_end": "",
        "fields": [],
        "error_message_zh": token["message_zh"] if not token["configured"] else "",
        "fallback_used": False,
        "cache_used": False,
        "last_success_time": "",
        "next_actions_zh": list(token["next_actions_zh"]),
        "rows": [],
    }


def _finish_result(result: dict[str, Any], rows: list[dict[str, Any]], output_file: str, message_zh: str) -> dict[str, Any]:
    result["attempted"] = True
    result["rows"] = rows
    result["row_count"] = len(rows)
    result["success"] = bool(rows)
    result["status"] = "success" if rows else "no_sn_rows"
    result["fields"] = sorted(rows[0].keys()) if rows else []
    result["date_start"] = rows[0].get("trade_date", "") if rows else ""
    result["date_end"] = rows[-1].get("trade_date", "") if rows else ""
    result["last_success_time"] = _now() if rows else ""
    result["message_zh"] = message_zh if rows else "Tushare 接口返回成功，但未发现沪锡/SN 相关行；未伪造数据。"
    result["error_message_zh"] = "" if rows else result["message_zh"]
    if rows:
        _write_json(
            _fundamentals_dir() / output_file,
            {
                "generated_at": _now(),
                "source": "tushare",
                "status": "success",
                "row_count": len(rows),
                "date_start": result["date_start"],
                "date_end": result["date_end"],
                "fields": result["fields"],
                "selected_params": result.get("selected_params", {}),
                "rows": rows,
                "message_zh": message_zh,
            },
        )
    return sanitize_for_json(result)


def test_tushare_connection(client: Any | None = None) -> dict[str, Any]:
    token = _token_status()
    if not token["configured"]:
        return sanitize_for_json({"success": False, **token})
    try:
        api = client or _get_client(resolve_secret("SN_TUSHARE_TOKEN").get("value"))
        frame = _frame_from_call(api, "fut_basic", exchange="SHFE")
        rows = [row for row in frame.to_dict("records") if _is_tin_row(row)]
        status = "success" if rows else "no_sn_rows"
        return sanitize_for_json(
            {
                "success": bool(rows),
                "configured": True,
                "source": token["source"],
                "masked": token["masked"],
                "status": status,
                "row_count": len(rows),
                "message_zh": "Tushare 连接成功并发现沪锡合约。" if rows else "Tushare 连接成功，但 fut_basic 未返回沪锡/SN 行。",
                "request_params_sanitized": {"api": "fut_basic", "exchange": "SHFE"},
            }
        )
    except Exception as exc:
        return sanitize_for_json(
            {
                "success": False,
                "configured": True,
                "source": token["source"],
                "masked": token["masked"],
                "status": _exception_status(exc),
                "error_message_zh": f"Tushare connection failed: {_safe_error_message(exc)}",
                "message_zh": "Tushare connection failed; check token, network, package, or interface permission.",
                "request_params_sanitized": {"api": "fut_basic", "exchange": "SHFE"},
            }
        )


def fetch_fut_basic(client: Any | None = None) -> dict[str, Any]:
    result = _base_result("tushare_futures", "fut_basic", {"exchange": "SHFE"})
    if result["status"] == "token_missing":
        return sanitize_for_json(result)
    try:
        api = client or _get_client(resolve_secret("SN_TUSHARE_TOKEN").get("value"))
        frame = _frame_from_call(api, "fut_basic", exchange="SHFE")
        rows: list[dict[str, Any]] = []
        for raw in frame.to_dict("records"):
            if not _is_tin_row(raw):
                continue
            rows.append(
                {
                    "contract": normalize_tushare_futures_symbol(raw.get("ts_code") or raw.get("symbol")),
                    "ts_code": str(raw.get("ts_code") or ""),
                    "name": str(raw.get("name") or raw.get("fut_name") or ""),
                    "exchange": str(raw.get("exchange") or "SHFE"),
                    "source": "tushare",
                    "from_cache": False,
                    "quality_flag": "real",
                }
            )
        return _finish_result(result, rows, "sn_tushare_contracts.json", "Tushare 沪锡合约信息已写入。")
    except Exception as exc:
        return _fail_result(result, exc, "fut_basic")


def fetch_trade_calendar(client: Any | None = None) -> dict[str, Any]:
    result = _base_result("tushare_futures", "trade_cal", {"exchange": "SHFE"})
    if result["status"] == "token_missing":
        return sanitize_for_json(result)
    try:
        api = client or _get_client(resolve_secret("SN_TUSHARE_TOKEN").get("value"))
        frame = _frame_from_call(api, "trade_cal", exchange="SHFE")
        rows = [
            {
                "trade_date": _date(raw.get("cal_date") or raw.get("trade_date")),
                "is_open": int(_numeric(raw.get("is_open")) or 0),
                "exchange": str(raw.get("exchange") or "SHFE"),
                "source": "tushare",
                "from_cache": False,
                "quality_flag": "real",
            }
            for raw in frame.to_dict("records")
            if raw.get("cal_date") or raw.get("trade_date")
        ]
        return _finish_result(result, rows, "sn_tushare_trade_calendar.json", "Tushare SHFE 交易日历已写入。")
    except Exception as exc:
        return _fail_result(result, exc, "trade_cal")


def fetch_sn_fut_daily(client: Any | None = None) -> dict[str, Any]:
    result = _base_result("tushare_futures", "fut_daily", {"ts_code": "SN.SHF", "exchange": "SHFE", "product": "SN"})
    if result["status"] == "token_missing":
        return sanitize_for_json(result)
    try:
        api = client or _get_client(resolve_secret("SN_TUSHARE_TOKEN").get("value"))
        frame = _frame_from_market_date_range(api, "fut_daily", ts_code="SN.SHF")
        if frame.empty:
            frame = _frame_from_market_date_range(api, "fut_daily", exchange="SHFE")
        rows = []
        for raw in frame.to_dict("records"):
            contract = normalize_tushare_futures_symbol(raw.get("ts_code") or raw.get("symbol") or raw.get("contract"))
            if not contract:
                continue
            rows.append(
                {
                    "trade_date": _date(raw.get("trade_date")),
                    "contract": contract,
                    "open": _numeric(raw.get("open")),
                    "high": _numeric(raw.get("high")),
                    "low": _numeric(raw.get("low")),
                    "close": _numeric(raw.get("close")),
                    "settlement": _numeric(raw.get("settle") if "settle" in raw else raw.get("settlement")),
                    "volume": _numeric(raw.get("vol") if "vol" in raw else raw.get("volume")),
                    "open_interest": _numeric(raw.get("oi") if "oi" in raw else raw.get("open_interest")),
                    "source": "tushare",
                    "from_cache": False,
                    "quality_flag": "real",
                }
            )
        rows = sorted([row for row in rows if row["trade_date"]], key=lambda row: (row["trade_date"], row["contract"]))
        return _finish_result(result, rows, "sn_tushare_daily.json", "Tushare 沪锡期货日线已写入。")
    except Exception as exc:
        return _fail_result(result, exc, "fut_daily")


def fetch_sn_warehouse_receipt(client: Any | None = None) -> dict[str, Any]:
    result = _base_result("tushare_futures", "fut_wsr", {"symbol": "SN", "product": "SN"})
    if result["status"] == "token_missing":
        return sanitize_for_json(result)
    try:
        api = client or _get_client(resolve_secret("SN_TUSHARE_TOKEN").get("value"))
        failed, seed_frame = _probe_or_fail(result, api, "fut_wsr")
        if failed is not None:
            return failed
        frame = _expand_selected_frame(api, "fut_wsr", result.get("selected_params", {}), seed_frame)
        rows = []
        for raw in frame.to_dict("records"):
            if not _is_aux_tin_row(raw):
                continue
            receipt = raw.get("warehouse_receipt")
            for key in ("warehouse_receipt", "receipt", "wsr", "vol", "value", "wh_receipt"):
                if key in raw and raw.get(key) not in (None, ""):
                    receipt = raw.get(key)
                    break
            rows.append(
                {
                    "trade_date": _date(raw.get("trade_date")),
                    "product": "SN",
                    "warehouse": str(raw.get("warehouse") or raw.get("warehouse_name") or raw.get("wh_name") or ""),
                    "warehouse_receipt": _numeric(receipt),
                    "warehouse_receipt_delta": None,
                    "warehouse_receipt_delta_1w": None,
                    "source": "tushare",
                    "from_cache": False,
                    "quality_flag": "real",
                }
            )
        rows = sorted([row for row in rows if row["trade_date"]], key=lambda row: (row["warehouse"], row["trade_date"]))
        previous_by_warehouse: dict[str, float | int | None] = {}
        history_by_warehouse: dict[str, list[float | int | None]] = {}
        for row in rows:
            warehouse = str(row.get("warehouse") or "")
            receipt = row.get("warehouse_receipt")
            previous = previous_by_warehouse.get(warehouse)
            row["warehouse_receipt_delta"] = _numeric(float(receipt) - float(previous)) if receipt is not None and previous is not None else None
            history = history_by_warehouse.setdefault(warehouse, [])
            row["warehouse_receipt_delta_1w"] = _numeric(float(receipt) - float(history[-5])) if receipt is not None and len(history) >= 5 and history[-5] is not None else None
            history.append(receipt)
            previous_by_warehouse[warehouse] = receipt
        rows = sorted(rows, key=lambda row: (row["trade_date"], row["warehouse"]))
        return _finish_result(result, rows, "sn_tushare_warehouse_receipt.json", "Tushare 沪锡仓单日报已写入。")
    except Exception as exc:
        return _fail_result(result, exc, "fut_wsr")


def fetch_sn_settlement(client: Any | None = None) -> dict[str, Any]:
    result = _base_result("tushare_futures", "fut_settle", {"ts_code": "SN.SHF", "product": "SN"})
    if result["status"] == "token_missing":
        return sanitize_for_json(result)
    try:
        api = client or _get_client(resolve_secret("SN_TUSHARE_TOKEN").get("value"))
        failed, seed_frame = _probe_or_fail(result, api, "fut_settle")
        if failed is not None:
            return failed
        frame = _expand_selected_frame(api, "fut_settle", result.get("selected_params", {}), seed_frame)
        rows = []
        for raw in frame.to_dict("records"):
            contract = normalize_tushare_futures_symbol(raw.get("ts_code") or raw.get("symbol") or raw.get("contract"))
            if not contract:
                continue
            rows.append(
                {
                    "trade_date": _date(raw.get("trade_date")),
                    "contract": contract,
                    "settlement": _numeric(raw.get("settle") if "settle" in raw else raw.get("settlement")),
                    "trading_fee_rate": _numeric(raw.get("trade_fee_rate") if "trade_fee_rate" in raw else raw.get("trading_fee_rate") if "trading_fee_rate" in raw else raw.get("fee_rate")),
                    "trading_fee": _numeric(raw.get("trade_fee") if "trade_fee" in raw else raw.get("trading_fee") if "trading_fee" in raw else raw.get("fee")),
                    "long_margin_rate": _numeric(raw.get("long_margin_rate") if "long_margin_rate" in raw else raw.get("long_margin") if "long_margin" in raw else raw.get("margin_rate")),
                    "short_margin_rate": _numeric(raw.get("short_margin_rate") if "short_margin_rate" in raw else raw.get("short_margin") if "short_margin" in raw else raw.get("margin_rate")),
                    "offset_today_fee": _numeric(raw.get("offset_today_fee") if "offset_today_fee" in raw else raw.get("offset_fee")),
                    "source": "tushare",
                    "from_cache": False,
                    "quality_flag": "real",
                }
            )
        rows = sorted([row for row in rows if row["trade_date"]], key=lambda row: (row["trade_date"], row["contract"]))
        return _finish_result(result, rows, "sn_tushare_settlement.json", "Tushare 沪锡结算参数已写入。")
    except Exception as exc:
        return _fail_result(result, exc, "fut_settle")


def fetch_sn_holding(client: Any | None = None) -> dict[str, Any]:
    result = _base_result("tushare_futures", "fut_holding", {"symbol": "SN", "product": "SN"})
    if result["status"] == "token_missing":
        return sanitize_for_json(result)
    try:
        api = client or _get_client(resolve_secret("SN_TUSHARE_TOKEN").get("value"))
        failed, seed_frame = _probe_or_fail(result, api, "fut_holding")
        if failed is not None:
            return failed
        frame = _expand_selected_frame(api, "fut_holding", result.get("selected_params", {}), seed_frame)
        rows = []
        for raw in frame.to_dict("records"):
            contract = normalize_tushare_futures_symbol(raw.get("ts_code") or raw.get("symbol") or raw.get("contract"))
            if not contract and not _is_aux_tin_row(raw):
                continue
            long_position = _numeric(raw.get("long_hld") if "long_hld" in raw else raw.get("long_position"))
            short_position = _numeric(raw.get("short_hld") if "short_hld" in raw else raw.get("short_position"))
            rows.append(
                {
                    "trade_date": _date(raw.get("trade_date")),
                    "contract_or_product": contract or "SN",
                    "member_name": str(raw.get("broker") or raw.get("member_name") or raw.get("name") or ""),
                    "long_position": long_position,
                    "short_position": short_position,
                    "member_net_position": _numeric(float(long_position) - float(short_position)) if long_position is not None and short_position is not None else None,
                    "long_change": _numeric(raw.get("long_chg") if "long_chg" in raw else raw.get("long_change")),
                    "short_change": _numeric(raw.get("short_chg") if "short_chg" in raw else raw.get("short_change")),
                    "rank": int(_numeric(raw.get("rank")) or 0),
                    "source": "tushare",
                    "from_cache": False,
                    "quality_flag": "real",
                }
            )
        rows = sorted([row for row in rows if row["trade_date"]], key=lambda row: (row["trade_date"], row["contract_or_product"], row["rank"]))
        return _finish_result(result, rows, "sn_tushare_holding.json", "Tushare 沪锡成交持仓排名已写入。")
    except Exception as exc:
        return _fail_result(result, exc, "fut_holding")


def normalize_tushare_rows(rows: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Public helper for diagnostics/tests: keep real SN rows only."""
    return [dict(row) for row in rows if _is_tin_row(row)]


def refresh_tushare_futures_data(client: Any | None = None, force: bool = False) -> dict[str, Any]:
    del force
    token = _token_status()
    api = client
    if token["configured"]:
        api = api or _get_client(resolve_secret("SN_TUSHARE_TOKEN").get("value"))
    results = {
        "tushare_connection": test_tushare_connection(client=api),
        "tushare_contracts": fetch_fut_basic(client=api),
        "tushare_trade_calendar": fetch_trade_calendar(client=api),
        "tushare_daily": fetch_sn_fut_daily(client=api),
    }
    probe_report: dict[str, Any] = {"status": token["status"], "results": {}, "success": False}
    if token["configured"] and api is not None:
        try:
            probe_report = build_tushare_param_probe_report(client=api)
        except Exception as exc:
            probe_report = {
                "status": _exception_status(exc),
                "success": False,
                "error_message_zh": _safe_error_message(exc),
                "results": {},
            }
    results.update(
        {
            "tushare_warehouse": fetch_sn_warehouse_receipt(client=api),
            "tushare_settlement": fetch_sn_settlement(client=api),
            "tushare_holding": fetch_sn_holding(client=api),
            "tushare_param_probe": probe_report,
        }
    )
    successes = [item for item in results.values() if isinstance(item, Mapping) and item.get("success")]
    attempted = [item for item in results.values() if isinstance(item, Mapping) and item.get("attempted")]
    status = "success" if len(successes) == len(results) else "partial_success" if successes else token["status"]
    payload = {
        "generated_at": _now(),
        "source": "tushare",
        "source_name": "tushare_futures",
        "configured": bool(token["configured"]),
        "config_source": token["source"],
        "masked": token["masked"],
        "status": status,
        "success": bool(successes),
        "partial_success": bool(successes) and len(successes) < len(results),
        "row_count": sum(int(item.get("row_count") or 0) for item in results.values() if isinstance(item, Mapping)),
        "results": results,
        "provider_attempts": list(results.values()),
        "attempted": bool(attempted),
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "message_zh": "Tushare 期货基础数据刷新完成；失败的辅助源不阻断主行情，不生成预测。",
        "next_actions_zh": token["next_actions_zh"] if not token["configured"] else ["查看 Tushare provider status 和字段覆盖率。"],
    }
    _write_json(_fundamentals_dir() / "tushare_provider_status.json", payload)
    return sanitize_for_json(payload)
