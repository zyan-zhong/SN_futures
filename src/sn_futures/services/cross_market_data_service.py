from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping, Sequence

import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..data_providers.alphavantage_provider import AlphaVantageProvider
from ..runtime import get_user_output_dir


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _fundamentals_dir() -> Path:
    path = get_user_output_dir() / "fundamentals"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")


def _date(row: Mapping[str, Any]) -> str:
    return str(row.get("trade_date") or row.get("date") or row.get("日期") or row.get("time") or "")[:10]


def _to_float(value: Any) -> float | None:
    try:
        number = float(value)
    except Exception:
        return None
    return number if pd.notna(number) else None


def _series_by_date(rows: Sequence[Mapping[str, Any]], value_keys: tuple[str, ...]) -> dict[str, float]:
    out: dict[str, float] = {}
    for row in rows:
        trade_date = _date(row)
        if not trade_date:
            continue
        value = None
        for key in value_keys:
            value = _to_float(row.get(key))
            if value is not None:
                break
        if value is not None:
            out[trade_date] = value
    return out


def build_cross_market_rows(
    lme_rows: Sequence[Mapping[str, Any]],
    fx_rows: Sequence[Mapping[str, Any]],
    macro_rows: Sequence[Mapping[str, Any]] | None = None,
    shfe_rows: Sequence[Mapping[str, Any]] | None = None,
) -> dict[str, Any]:
    lme = _series_by_date(lme_rows, ("lme_tin_close", "close", "price"))
    fx = _series_by_date(fx_rows, ("usd_cny", "close", "price"))
    dxy = _series_by_date(macro_rows or [], ("dxy",))
    us10y = _series_by_date(macro_rows or [], ("us10y", "us10y_yield", "yield"))
    shfe = _series_by_date(shfe_rows or [], ("close", "futures_close"))
    dates = sorted(set(lme) | set(fx) | set(dxy) | set(us10y) | set(shfe))
    rows = [
        {
            "trade_date": date,
            "lme_tin_close": lme.get(date),
            "usd_cny": fx.get(date),
            "dxy": dxy.get(date),
            "us10y": us10y.get(date),
            "shfe_close": shfe.get(date),
        }
        for date in dates
    ]
    if not rows or not lme or not fx:
        return {"success": False, "rows": [], "message_zh": "缺 LME 锡价或 USD/CNY，跨市场因子不可用。"}
    frame = pd.DataFrame(rows)
    for col in ("lme_tin_close", "usd_cny", "dxy", "us10y", "shfe_close"):
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    frame["lme_tin_return_1d"] = frame["lme_tin_close"].pct_change(1, fill_method=None)
    frame["lme_tin_return_3d"] = frame["lme_tin_close"].pct_change(3, fill_method=None)
    frame["usd_cny_return"] = frame["usd_cny"].pct_change(1, fill_method=None)
    frame["dxy_return"] = frame["dxy"].pct_change(1, fill_method=None)
    frame["us10y_change"] = frame["us10y"].diff(1)
    frame["lme_shfe_spread"] = frame["lme_tin_close"] * frame["usd_cny"] - frame["shfe_close"]
    return {"success": True, "rows": frame.where(pd.notna(frame), None).to_dict(orient="records"), "message_zh": "跨市场数据已标准化。"}


def _parse_alpha_fx(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("Time Series FX (Daily)")
    if not isinstance(raw, Mapping):
        return []
    rows = []
    for date, values in raw.items():
        if isinstance(values, Mapping):
            rows.append({"trade_date": str(date), "usd_cny": _to_float(values.get("4. close"))})
    return rows


def _parse_alpha_treasury(payload: Mapping[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("data")
    if not isinstance(raw, list):
        return []
    rows = []
    for item in raw:
        if isinstance(item, Mapping):
            rows.append({"trade_date": str(item.get("date") or "")[:10], "us10y": _to_float(item.get("value"))})
    return rows


def refresh_cross_market_data(force: bool = False) -> dict[str, Any]:
    _ = force
    out = _fundamentals_dir()
    path = out / "sn_cross_market.json"
    status_path = out / "cross_market_status.json"

    provider = AlphaVantageProvider()
    attempts: list[dict[str, Any]] = []
    fx_rows: list[dict[str, Any]] = []
    macro_rows: list[dict[str, Any]] = []
    if provider.api_key:
        fx = provider.fetch_fx_daily(from_symbol="USD", to_symbol="CNY", outputsize="compact")
        attempts.append({"provider": "alphavantage_fx_daily", "success": bool(fx.get("success")), "from_cache": bool(fx.get("from_cache")), "message_zh": fx.get("message")})
        if isinstance(fx.get("data"), Mapping):
            fx_rows = _parse_alpha_fx(fx["data"])
        tsy = provider.fetch_treasury_yield(interval="daily", maturity="10year")
        attempts.append({"provider": "alphavantage_treasury_yield", "success": bool(tsy.get("success")), "from_cache": bool(tsy.get("from_cache")), "message_zh": tsy.get("message")})
        if isinstance(tsy.get("data"), Mapping):
            macro_rows = _parse_alpha_treasury(tsy["data"])
    else:
        attempts.append({"provider": "alphavantage", "success": False, "error_code": "not_configured", "message_zh": "未配置 SN_ALPHA_VANTAGE_KEY。"})

    result = build_cross_market_rows([], fx_rows, macro_rows, [])
    payload = {"generated_at": _now(), "sample": False, "rows": result["rows"], "message_zh": result["message_zh"], "provider_attempts": attempts}
    status = {
        "source_name": "cross_market",
        "enabled": True,
        "configured": bool(provider.api_key),
        "attempted": True,
        "success": bool(result["success"]),
        "from_cache": any(bool(item.get("from_cache")) for item in attempts),
        "freshness_label": "正常" if result["success"] else ("未配置" if not provider.api_key else "请求失败"),
        "last_attempt_time": _now(),
        "last_success_time": _now() if result["success"] else "",
        "row_count": len(result["rows"]),
        "error_code": "" if result["success"] else ("lme_tin_missing" if fx_rows else "not_configured"),
        "message_zh": result["message_zh"],
        "next_actions_zh": ["接入 LME 锡收盘价", "配置 Alpha Vantage 获取 USD/CNY 和 US10Y", "不要将宏观源当作沪锡主行情"],
        "provider_attempts": attempts,
    }
    _write_json(path, payload)
    _write_json(status_path, status)
    return sanitize_for_json(
        {
            "status": "success" if result["success"] else "skipped",
            "message_zh": result["message_zh"],
            "row_count": len(result["rows"]),
            "output_files": [str(path), str(status_path)],
            "provider_attempts": attempts,
            "next_actions_zh": status["next_actions_zh"],
        }
    )
