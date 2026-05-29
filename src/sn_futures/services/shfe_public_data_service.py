from __future__ import annotations

import importlib
import json
import time
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


AKSHARE_CANDIDATES = (
    "futures_inventory_99",
    "futures_inventory_em",
    "futures_warehouse_receipt",
    "futures_spot_price",
    "futures_delivery_match",
    "futures_zh_daily_sina",
    "futures_zh_daily",
    "futures_hist_table_em",
    "futures_contract_info_shfe",
    "futures_member_position_rank",
    "futures_czce_warehouse_receipt",
    "futures_dce_warehouse_receipt",
)

TIN_TOKENS = ("锡", "沪锡", "SN", "sn")
WAF_TOKENS = ("人机验证", "captcha", "waf", "安全验证", "访问验证", "cloudflare", "verify")


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


def _as_float(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        text = str(value).replace(",", "").replace("%", "").strip()
        number = float(text)
    except Exception:
        return None
    return number if np.isfinite(number) else None


def _date_value(value: Any) -> str:
    parsed = pd.to_datetime(value, errors="coerce")
    if pd.isna(parsed):
        return ""
    return pd.Timestamp(parsed).strftime("%Y-%m-%d")


def _akshare_module(module: Any | None = None) -> Any | None:
    if module is not None:
        return module
    try:
        return importlib.import_module("akshare")
    except Exception:
        return None


def _attempt(
    *,
    provider_name: str,
    function_name: str,
    started_at: str,
    started_perf: float,
    attempted: bool = True,
    success: bool = False,
    status: str = "failed",
    row_count: int = 0,
    fields: Sequence[str] | None = None,
    params_sanitized: Mapping[str, Any] | None = None,
    error_message_zh: str = "",
    fallback_used: bool = False,
    cache_used: bool = False,
    last_success_time: str = "",
    date_start: str = "",
    date_end: str = "",
    next_actions_zh: Sequence[str] | None = None,
) -> dict[str, Any]:
    return {
        "provider_name": provider_name,
        "function_name": function_name,
        "params_sanitized": dict(params_sanitized or {}),
        "attempted": attempted,
        "success": success,
        "status": status,
        "row_count": int(row_count or 0),
        "date_start": date_start,
        "date_end": date_end,
        "fields": list(fields or []),
        "error_message_zh": error_message_zh,
        "fallback_used": fallback_used,
        "cache_used": cache_used,
        "last_success_time": last_success_time,
        "last_attempt_time": started_at,
        "started_at": started_at,
        "finished_at": _now(),
        "duration_seconds": round(time.perf_counter() - started_perf, 6),
        "next_actions_zh": list(next_actions_zh or []),
    }


def normalize_tin_symbol(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    upper = text.upper()
    if "锡" in text or "沪锡" in text or "閿" in text or "娌" in text:
        return "SN"
    if "锡" in text or "沪锡" in text or upper.startswith("SN"):
        return "SN"
    return upper


def _to_frame(payload: Any) -> pd.DataFrame:
    if payload is None:
        return pd.DataFrame()
    if isinstance(payload, pd.DataFrame):
        return payload.copy()
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    if isinstance(payload, Mapping):
        rows = payload.get("rows") or payload.get("data") or payload.get("items") or []
        return pd.DataFrame(rows)
    return pd.DataFrame()


def _contains_tin(value: Any) -> bool:
    text = str(value or "")
    if not text:
        return False
    if "锡" in text or "沪锡" in text or "閿" in text or "娌" in text:
        return True
    if "锡" in text or "沪锡" in text:
        return True
    upper = text.upper()
    return upper == "SN" or upper.startswith("SN") or ".SN" in upper or "SN." in upper


def _tin_rows(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame
    preferred = [col for col in frame.columns if any(token in str(col).lower() for token in ("品种", "合约", "symbol", "variety", "commodity", "name", "代码"))]
    columns = preferred or list(frame.columns)
    mask = pd.Series(False, index=frame.index)
    for col in columns:
        mask = mask | frame[col].map(_contains_tin)
    return frame[mask].copy()


def _has_identity_column(frame: pd.DataFrame) -> bool:
    tokens = ("鍝佺", "鍚堢害", "symbol", "variety", "commodity", "name", "浠ｇ爜")
    return any(token in str(col).lower() for col in frame.columns for token in tokens)


def normalize_date_and_numeric_fields(rows: Sequence[Mapping[str, Any]], numeric_fields: Sequence[str]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        trade_date = (
            row.get("trade_date")
            or row.get("date")
            or row.get("日期")
            or row.get("统计日期")
            or row.get("交易日期")
            or row.get("time")
        )
        parsed_date = _date_value(trade_date)
        if not parsed_date:
            continue
        item = dict(row)
        item["trade_date"] = parsed_date
        for field in numeric_fields:
            if field in item:
                item[field] = _as_float(item[field])
        normalized.append(item)
    return normalized


def detect_shfe_direct_access(fetcher: Callable[[], str] | None = None) -> dict[str, Any]:
    started_at = _now()
    started_perf = time.perf_counter()
    try:
        if fetcher is None:
            with urllib.request.urlopen("https://www.shfe.com.cn/", timeout=5) as response:
                text = response.read(4096).decode("utf-8", errors="ignore")
        else:
            text = fetcher()
        lowered = text.lower()
        real_waf_tokens = ("人机验证", "安全验证", "访问验证", "验证码", "captcha", "waf", "cloudflare", "verify")
        if any(token.lower() in lowered for token in WAF_TOKENS + real_waf_tokens):
            status = "blocked_by_waf"
            message = "SHFE 官网直连被人机验证阻断；系统已尝试 AKShare/缓存辅助源。该状态不影响主行情链路。"
            success = False
        elif "shfe" in lowered or "上海期货交易所" in text:
            status = "accessible"
            message = "SHFE 官网直连可访问，但仍优先使用结构化 AKShare/缓存辅助源。"
            success = True
        else:
            status = "unavailable"
            message = "SHFE 官网返回非预期页面，未作为结构化数据源使用。"
            success = False
        return _attempt(
            provider_name="shfe_direct",
            function_name="detect_shfe_direct_access",
            started_at=started_at,
            started_perf=started_perf,
            success=success,
            status=status,
            row_count=0,
            error_message_zh="" if success else message,
            next_actions_zh=["若被 WAF 阻断，使用 AKShare 或最近成功缓存作为辅助源。"],
        ) | {"message_zh": message}
    except Exception as exc:
        return _attempt(
            provider_name="shfe_direct",
            function_name="detect_shfe_direct_access",
            started_at=started_at,
            started_perf=started_perf,
            success=False,
            status="unavailable",
            error_message_zh=f"SHFE 官网直连不可用：{exc}",
            next_actions_zh=["无需反复重试官网直连；优先检查 AKShare 辅助源和缓存。"],
        ) | {"message_zh": f"SHFE 官网直连不可用：{exc}"}


def _call_with_candidates(fn: Callable[..., Any], candidates: Sequence[Mapping[str, Any]]) -> tuple[pd.DataFrame, dict[str, Any], str]:
    last_error = ""
    fallback_frame = pd.DataFrame()
    fallback_params: dict[str, Any] = dict(candidates[0] if candidates else {})
    for params in candidates:
        try:
            payload = fn(**dict(params))
            frame = _to_frame(payload)
            if not frame.empty:
                params_are_tin = any(_contains_tin(value) for value in dict(params).values())
                if (params_are_tin and not _has_identity_column(frame)) or not _tin_rows(frame).empty:
                    return frame, dict(params), ""
                if fallback_frame.empty:
                    fallback_frame = frame
                    fallback_params = dict(params)
                    continue
            return frame, dict(params), ""
        except TypeError as exc:
            last_error = str(exc)
            try:
                payload = fn()
                frame = _to_frame(payload)
                return frame, {}, ""
            except Exception as inner:
                last_error = str(inner)
        except Exception as exc:
            last_error = str(exc)
    if not fallback_frame.empty:
        return fallback_frame, fallback_params, ""
    return pd.DataFrame(), dict(candidates[0] if candidates else {}), last_error


def probe_akshare_futures_fundamental_functions(ak_module: Any | None = None) -> dict[str, Any]:
    ak = _akshare_module(ak_module)
    rows: list[dict[str, Any]] = []
    if ak is None:
        for name in AKSHARE_CANDIDATES:
            rows.append({"function_name": name, "exists": False, "callable": False, "status": "akshare_unavailable", "columns": [], "tin_row_count": 0})
        return {"success": False, "functions": rows, "message_zh": "当前环境未安装或无法导入 AKShare。"}
    for name in AKSHARE_CANDIDATES:
        fn = getattr(ak, name, None)
        if not callable(fn):
            rows.append({"function_name": name, "exists": False, "callable": False, "status": "function_unavailable", "columns": [], "tin_row_count": 0})
            continue
        frame, params, error = _call_with_candidates(fn, _probe_params(name))
        tin = _tin_rows(frame)
        if tin.empty and any(_contains_tin(value) for value in params.values()) and not _has_identity_column(frame):
            tin = frame.copy()
        rows.append(
            {
                "function_name": name,
                "exists": True,
                "callable": True,
                "status": "success" if len(tin) else "no_tin_rows" if error == "" else "request_failed",
                "params_sanitized": params,
                "columns": [str(col) for col in frame.columns],
                "row_count": int(len(frame)),
                "tin_row_count": int(len(tin)),
                "error_message_zh": "" if error == "" else f"{name} 调用失败：{error}",
            }
        )
    return sanitize_for_json(
        {
            "success": any(row.get("tin_row_count", 0) for row in rows),
            "functions": rows,
            "message_zh": "AKShare 期货基础数据函数探测完成。",
        }
    )


def _probe_params(name: str) -> list[dict[str, Any]]:
    today = datetime.now().strftime("%Y%m%d")
    if name == "futures_zh_daily_sina":
        return [{"symbol": "SN0"}, {"symbol": "sn0"}, {"symbol": "SN"}, {"symbol": "sn"}]
    if name == "futures_zh_daily":
        return [{"symbol": "SN0"}, {"symbol": "sn0"}, {"symbol": "SN"}, {"symbol": "sn"}]
    if name == "futures_member_position_rank":
        return [{"date": today, "symbol": "SN"}, {"date": today, "variety": "SN"}, {"date": today}]
    if name in {"futures_inventory_99", "futures_inventory_em", "futures_warehouse_receipt", "futures_spot_price"}:
        return [{"exchange": "上海期货交易所"}, {"symbol": "SN"}, {}]
    if name == "futures_hist_table_em":
        return [{"symbol": "SN"}, {"symbol": "沪锡"}, {}]
    return [{}]


def _status_payload(
    name: str,
    *,
    success: bool,
    status: str,
    rows: Sequence[Mapping[str, Any]],
    attempts: Sequence[Mapping[str, Any]],
    output_file: Path,
    message_zh: str,
) -> dict[str, Any]:
    generated_at = _now()
    return sanitize_for_json(
        {
            "source_name": name,
            "enabled": True,
            "configured": True,
            "attempted": True,
            "success": bool(success),
            "status": status,
            "freshness_label": "正常" if success else "无锡数据" if status == "no_tin_rows" else "函数不可用" if status == "function_unavailable" else "请求失败",
            "from_cache": False,
            "row_count": len(rows),
            "last_attempt_time": generated_at,
            "last_success_time": generated_at if success else "",
            "message_zh": message_zh,
            "error_message_zh": "" if success else message_zh,
            "next_actions_zh": ["检查 AKShare 版本和网络。", "若函数返回无锡数据，不要用其它品种冒充锡。"],
            "attempts": list(attempts),
            "output_file": str(output_file),
        }
    )


def _write_rows(path: Path, rows: Sequence[Mapping[str, Any]], message: str) -> None:
    _write_json(
        path,
        {
            "generated_at": _now(),
            "sample": False,
            "rows": list(rows),
            "message_zh": message,
        },
    )


def _generic_fetch(
    *,
    name: str,
    output_file: str,
    functions: Sequence[str],
    normalizer: Callable[[pd.DataFrame], list[dict[str, Any]]],
    ak_module: Any | None = None,
) -> dict[str, Any]:
    ak = _akshare_module(ak_module)
    out = _fundamentals_dir() / output_file
    attempts: list[dict[str, Any]] = []
    if ak is None:
        status = _status_payload(
            name,
            success=False,
            status="function_unavailable",
            rows=[],
            attempts=[],
            output_file=out,
            message_zh="当前环境无法导入 AKShare，未获取真实辅助数据。",
        )
        _write_rows(out, [], status["message_zh"])
        return status
    for func_name in functions:
        started_at = _now()
        started_perf = time.perf_counter()
        fn = getattr(ak, func_name, None)
        if not callable(fn):
            attempts.append(
                _attempt(
                    provider_name="akshare",
                    function_name=func_name,
                    started_at=started_at,
                    started_perf=started_perf,
                    status="function_unavailable",
                    error_message_zh=f"AKShare 当前版本不存在 {func_name}。",
                    next_actions_zh=["升级 AKShare 或使用其它公开辅助源。"],
                )
            )
            continue
        frame, params, error = _call_with_candidates(fn, _probe_params(func_name))
        tin = _tin_rows(frame)
        if tin.empty and any(_contains_tin(value) for value in params.values()) and not _has_identity_column(frame):
            tin = frame.copy()
        if error:
            attempts.append(
                _attempt(
                    provider_name="akshare",
                    function_name=func_name,
                    started_at=started_at,
                    started_perf=started_perf,
                    status="request_failed",
                    fields=[str(col) for col in frame.columns],
                    params_sanitized=params,
                    error_message_zh=f"{func_name} 请求失败：{error}",
                )
            )
            continue
        if tin.empty:
            attempts.append(
                _attempt(
                    provider_name="akshare",
                    function_name=func_name,
                    started_at=started_at,
                    started_perf=started_perf,
                    status="no_tin_rows",
                    fields=[str(col) for col in frame.columns],
                    params_sanitized=params,
                    row_count=len(frame),
                    error_message_zh=f"{func_name} 返回数据中未识别到锡/SN 行。",
                )
            )
            continue
        rows = normalizer(tin)
        if rows:
            attempts.append(
                _attempt(
                    provider_name="akshare",
                    function_name=func_name,
                    started_at=started_at,
                    started_perf=started_perf,
                    success=True,
                    status="success",
                    fields=[str(col) for col in tin.columns],
                    params_sanitized=params,
                    row_count=len(rows),
                    date_start=rows[0].get("trade_date", ""),
                    date_end=rows[-1].get("trade_date", ""),
                    last_success_time=_now(),
                )
            )
            message = f"{name} 已通过 AKShare {func_name} 获取并标准化。"
            _write_rows(out, rows, message)
            return _status_payload(name, success=True, status="success", rows=rows, attempts=attempts, output_file=out, message_zh=message)
        attempts.append(
            _attempt(
                provider_name="akshare",
                function_name=func_name,
                started_at=started_at,
                started_perf=started_perf,
                status="missing_required_columns",
                fields=[str(col) for col in tin.columns],
                params_sanitized=params,
                row_count=len(tin),
                error_message_zh=f"{func_name} 有锡行但缺少可标准化字段。",
            )
        )
    final_status = "function_unavailable" if all(item.get("status") == "function_unavailable" for item in attempts) else "no_tin_rows"
    message = f"{name} 未获取到可用锡数据；已记录函数探测结果，未伪造字段。"
    _write_rows(out, [], message)
    return _status_payload(name, success=False, status=final_status, rows=[], attempts=attempts, output_file=out, message_zh=message)


def _pick(row: Mapping[str, Any], names: Sequence[str]) -> Any:
    lowered = {str(k).lower(): v for k, v in row.items()}
    for name in names:
        if name in row:
            return row[name]
        if name.lower() in lowered:
            return lowered[name.lower()]
    return None


def _normalize_inventory(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        value = _as_float(_pick(raw, ("shfe_inventory", "inventory", "库存", "库存量", "仓库库存", "数量", "小计")))
        date = _date_value(_pick(raw, ("trade_date", "date", "日期", "统计日期")))
        if value is None or not date:
            continue
        rows.append({"trade_date": date, "shfe_inventory": value, "source": "akshare", "from_cache": False, "quality_flag": "real"})
    rows = sorted(rows, key=lambda row: row["trade_date"])
    frame_out = pd.DataFrame(rows)
    if frame_out.empty:
        return []
    frame_out["inventory_delta_1w"] = pd.to_numeric(frame_out["shfe_inventory"], errors="coerce").diff(5)
    frame_out["inventory_delta_4w"] = pd.to_numeric(frame_out["shfe_inventory"], errors="coerce").diff(20)
    return frame_out.where(pd.notna(frame_out), None).to_dict(orient="records")


def _normalize_receipts(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        value = _as_float(_pick(raw, ("shfe_warehouse_receipt", "warehouse_receipt", "注册仓单", "仓单", "仓单量", "数量", "小计")))
        date = _date_value(_pick(raw, ("trade_date", "date", "日期", "统计日期")))
        if value is None or not date:
            continue
        rows.append({"trade_date": date, "shfe_warehouse_receipt": value, "source": "akshare", "from_cache": False, "quality_flag": "real"})
    rows = sorted(rows, key=lambda row: row["trade_date"])
    frame_out = pd.DataFrame(rows)
    if frame_out.empty:
        return []
    frame_out["warehouse_receipt_delta_1w"] = pd.to_numeric(frame_out["shfe_warehouse_receipt"], errors="coerce").diff(5)
    return frame_out.where(pd.notna(frame_out), None).to_dict(orient="records")


def _normalize_spot_basis(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        spot = _as_float(_pick(raw, ("spot_price", "现货价格", "价格", "报价", "平均价", "均价")))
        futures = _as_float(_pick(raw, ("futures_close", "close", "期货收盘", "收盘价", "主力收盘")))
        premium = _as_float(_pick(raw, ("spot_premium", "升贴水", "premium", "现货升贴水"))) or 0.0
        date = _date_value(_pick(raw, ("trade_date", "date", "日期", "统计日期")))
        if spot is None or not date:
            continue
        rows.append(
            {
                "trade_date": date,
                "spot_price": spot,
                "futures_close": futures,
                "spot_premium": premium,
                "spot_futures_basis": spot - futures if futures else None,
                "source": "akshare",
                "from_cache": False,
                "quality_flag": "real",
            }
        )
    rows = sorted(rows, key=lambda row: row["trade_date"])
    frame_out = pd.DataFrame(rows)
    if frame_out.empty:
        return []
    basis = pd.to_numeric(frame_out["spot_futures_basis"], errors="coerce")
    frame_out["basis_zscore_60"] = (basis - basis.rolling(60).mean()) / basis.rolling(60).std()
    frame_out["basis_percentile_252"] = basis.rolling(252).rank(pct=True)
    frame_out["cash_tightness_score"] = frame_out["basis_zscore_60"].fillna(0.0)
    return frame_out.where(pd.notna(frame_out), None).to_dict(orient="records")


def _normalize_exchange_daily(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        date = _date_value(_pick(raw, ("trade_date", "date", "日期", "time")))
        close = _as_float(_pick(raw, ("close", "收盘", "收盘价")))
        if close is None or not date:
            continue
        rows.append(
            {
                "trade_date": date,
                "contract": str(_pick(raw, ("contract", "合约", "symbol", "代码")) or "SN"),
                "open": _as_float(_pick(raw, ("open", "开盘", "开盘价"))),
                "high": _as_float(_pick(raw, ("high", "最高", "最高价"))),
                "low": _as_float(_pick(raw, ("low", "最低", "最低价"))),
                "close": close,
                "settlement": _as_float(_pick(raw, ("settlement", "结算价", "结算"))),
                "volume": _as_float(_pick(raw, ("volume", "成交量"))),
                "open_interest": _as_float(_pick(raw, ("open_interest", "持仓量", "持仓"))),
                "source": "akshare",
                "from_cache": False,
                "quality_flag": "real",
            }
        )
    return sorted(rows, key=lambda row: row["trade_date"])


def _normalize_member_positions(frame: pd.DataFrame) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for raw in frame.to_dict(orient="records"):
        date = _date_value(_pick(raw, ("trade_date", "date", "日期")))
        if not date:
            continue
        rows.append(
            {
                "trade_date": date,
                "contract": str(_pick(raw, ("contract", "合约", "symbol", "代码")) or "SN"),
                "rank": _as_float(_pick(raw, ("rank", "排名", "名次"))),
                "member_name": str(_pick(raw, ("member_name", "会员简称", "会员名称", "机构")) or ""),
                "long_position": _as_float(_pick(raw, ("long_position", "多头持仓", "买持仓"))),
                "short_position": _as_float(_pick(raw, ("short_position", "空头持仓", "卖持仓"))),
                "net_position": _as_float(_pick(raw, ("net_position", "净持仓"))),
                "source": "akshare",
                "from_cache": False,
                "quality_flag": "real",
            }
        )
    return rows


def fetch_shfe_inventory_via_akshare(ak_module: Any | None = None) -> dict[str, Any]:
    return _generic_fetch(
        name="AKShare SHFE 锡库存",
        output_file="sn_shfe_inventory.json",
        functions=("futures_inventory_99", "futures_inventory_em"),
        normalizer=_normalize_inventory,
        ak_module=ak_module,
    )


def fetch_shfe_warehouse_receipt_via_akshare(ak_module: Any | None = None) -> dict[str, Any]:
    return _generic_fetch(
        name="AKShare SHFE 锡注册仓单",
        output_file="sn_shfe_warehouse_receipts.json",
        functions=("futures_warehouse_receipt", "futures_inventory_99"),
        normalizer=_normalize_receipts,
        ak_module=ak_module,
    )


def fetch_spot_basis_via_akshare(ak_module: Any | None = None) -> dict[str, Any]:
    return _generic_fetch(
        name="AKShare 现货锡/基差",
        output_file="sn_spot_basis.json",
        functions=("futures_spot_price", "futures_delivery_match"),
        normalizer=_normalize_spot_basis,
        ak_module=ak_module,
    )


def fetch_exchange_daily_via_akshare(ak_module: Any | None = None) -> dict[str, Any]:
    return _generic_fetch(
        name="AKShare SHFE 交易所日线",
        output_file="sn_exchange_daily.json",
        functions=("futures_zh_daily_sina", "futures_zh_daily", "futures_hist_table_em"),
        normalizer=_normalize_exchange_daily,
        ak_module=ak_module,
    )


def fetch_member_position_via_akshare(ak_module: Any | None = None) -> dict[str, Any]:
    return _generic_fetch(
        name="AKShare SHFE 会员持仓排名",
        output_file="sn_member_positions.json",
        functions=("futures_member_position_rank",),
        normalizer=_normalize_member_positions,
        ak_module=ak_module,
    )


def _mirror_feature_files(results: Mapping[str, Mapping[str, Any]]) -> None:
    fundamentals = _fundamentals_dir()
    inv = _read_json(fundamentals / "sn_shfe_inventory.json")
    receipts = _read_json(fundamentals / "sn_shfe_warehouse_receipts.json")
    basis = _read_json(fundamentals / "sn_spot_basis.json")
    if isinstance(inv, Mapping):
        inv_rows = inv.get("rows") if isinstance(inv.get("rows"), list) else []
    else:
        inv_rows = []
    if isinstance(receipts, Mapping):
        receipt_rows = receipts.get("rows") if isinstance(receipts.get("rows"), list) else []
    else:
        receipt_rows = []
    if inv_rows or receipt_rows:
        by_date: dict[str, dict[str, Any]] = {}
        for row in inv_rows:
            if isinstance(row, Mapping) and row.get("trade_date"):
                by_date.setdefault(str(row["trade_date"]), {}).update(row)
        for row in receipt_rows:
            if isinstance(row, Mapping) and row.get("trade_date"):
                by_date.setdefault(str(row["trade_date"]), {}).update(row)
        combined = [dict(value) for _, value in sorted(by_date.items())]
        _write_rows(fundamentals / "sn_inventory.json", combined, "SHFE 库存/仓单已合并到因子输入。")
        _write_rows(fundamentals / "sn_warehouse_receipts.json", receipt_rows, "SHFE 仓单已写入因子输入。")
    if isinstance(basis, Mapping):
        _write_json(fundamentals / "sn_spot_basis.json", basis)


def refresh_shfe_public_data(force: bool = False, ak_module: Any | None = None, direct_fetcher: Callable[[], str] | None = None) -> dict[str, Any]:
    _ = force
    direct = detect_shfe_direct_access(fetcher=direct_fetcher)
    probe = probe_akshare_futures_fundamental_functions(ak_module=ak_module)
    results = {
        "shfe_direct_probe": direct,
        "akshare_function_probe": probe,
        "shfe_inventory": fetch_shfe_inventory_via_akshare(ak_module=ak_module),
        "shfe_warehouse_receipts": fetch_shfe_warehouse_receipt_via_akshare(ak_module=ak_module),
        "spot_basis": fetch_spot_basis_via_akshare(ak_module=ak_module),
        "exchange_daily": fetch_exchange_daily_via_akshare(ak_module=ak_module),
        "member_positions": fetch_member_position_via_akshare(ak_module=ak_module),
    }
    _mirror_feature_files(results)
    steps = [value for key, value in results.items() if key not in {"shfe_direct_probe", "akshare_function_probe"} and isinstance(value, Mapping)]
    success_count = sum(1 for value in steps if value.get("success"))
    status = "success" if success_count == len(steps) else "partial_success" if success_count else "failed"
    payload = {
        "generated_at": _now(),
        "status": status,
        "success": success_count > 0,
        "partial_success": 0 < success_count < len(steps),
        "message_zh": "SHFE/AKShare 辅助基本面源刷新完成；官网 WAF 不作为主行情 fatal failure。",
        "results": results,
        "output_files": [
            str(_fundamentals_dir() / "shfe_public_provider_status.json"),
            str(_fundamentals_dir() / "sn_shfe_inventory.json"),
            str(_fundamentals_dir() / "sn_shfe_warehouse_receipts.json"),
            str(_fundamentals_dir() / "sn_spot_basis.json"),
            str(_fundamentals_dir() / "sn_exchange_daily.json"),
            str(_fundamentals_dir() / "sn_member_positions.json"),
        ],
        "next_actions_zh": ["若部分源函数不可用，请升级 AKShare 或检查网络。", "无锡数据时不能用其它品种替代。"],
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
    }
    _write_json(_fundamentals_dir() / "shfe_public_provider_status.json", payload)
    return sanitize_for_json(payload)
