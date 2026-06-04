from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text


REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "fut_wsr": ("trade_date",),
    "fut_settle": ("trade_date", "ts_code", "settle"),
    "fut_holding": ("trade_date", "long_hld", "short_hld"),
}


@dataclass
class ProbeOutcome:
    report: dict[str, Any]
    frame: pd.DataFrame


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


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(sanitize_mapping(dict(payload))), ensure_ascii=False, indent=2), encoding="utf-8")


def _date_yyyymmdd(value: Any) -> str:
    parsed = pd.to_datetime(str(value or "").strip(), errors="coerce")
    if pd.isna(parsed):
        return ""
    return pd.Timestamp(parsed).strftime("%Y%m%d")


def _market_dates(limit: int = 6) -> list[str]:
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
        parsed = _date_yyyymmdd(row.get("trade_date") or row.get("date") or row.get("time"))
        if parsed:
            dates.append(parsed)
    return sorted(set(dates), reverse=True)[: max(1, int(limit))]


def _contract_codes(limit: int = 6) -> list[str]:
    payload = _read_json(_fundamentals_dir() / "sn_tushare_contracts.json")
    rows = payload.get("rows") if isinstance(payload, Mapping) else payload if isinstance(payload, list) else []
    codes: list[str] = []
    for row in rows if isinstance(rows, list) else []:
        if not isinstance(row, Mapping):
            continue
        raw = str(row.get("ts_code") or row.get("contract") or row.get("symbol") or "").strip().upper()
        if not raw.startswith("SN"):
            continue
        if "." not in raw:
            raw = f"{raw}.SHF"
        codes.append(raw)
    if "SN.SHF" not in codes:
        codes.append("SN.SHF")
    return list(dict.fromkeys(codes))[: max(1, int(limit))]


def _frame_from_call(client: Any, method: str, params: Mapping[str, Any]) -> pd.DataFrame:
    payload = getattr(client, method)(**dict(params))
    if isinstance(payload, pd.DataFrame):
        return payload.copy()
    if isinstance(payload, list):
        return pd.DataFrame(payload)
    return pd.DataFrame()


def _sanitize_params(params: Mapping[str, Any]) -> dict[str, Any]:
    return sanitize_for_json({key: value for key, value in params.items() if value not in (None, "")})


def classify_tushare_error(exc: Exception | str) -> str:
    text = str(exc).lower()
    if "tushare_package_missing" in text:
        return "tushare_package_missing"
    if any(token in text for token in ("permission", "forbidden", "unauthorized", "no access", "权限", "无权限", "没有访问")):
        return "permission_denied"
    if any(token in text for token in ("quota", "积分", "频率", "rate limit", "frequency", "limit", "insufficient", "访问次数", "每分钟")):
        return "quota_limited"
    if any(token in text for token in ("token", "invalid", "认证", "auth")):
        return "key_invalid"
    if any(token in text for token in ("timeout", "connection", "network", "网络", "连接")):
        return "network_failed"
    if any(token in text for token in ("schema", "column", "columns", "missing field", "字段")):
        return "schema_mismatch"
    return "request_failed"


def validate_required_columns(api_name: str, columns: Iterable[Any]) -> dict[str, Any]:
    required = REQUIRED_COLUMNS.get(str(api_name), ())
    observed = {str(column) for column in columns}
    missing = [column for column in required if column not in observed]
    ok = not missing
    return {
        "ok": ok,
        "status": "success" if ok else "schema_mismatch",
        "missing_columns": missing,
        "observed_columns": sorted(observed),
    }


def _looks_like_sn(frame: pd.DataFrame, api_name: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    data = frame.copy()
    if api_name == "fut_wsr":
        for column in ("symbol", "product", "variety"):
            if column in data.columns:
                mask = data[column].astype(str).str.upper().str.contains("SN|锡|沪锡", regex=True, na=False)
                if bool(mask.any()):
                    return data.loc[mask].copy()
        return data
    for column in ("ts_code", "symbol", "contract"):
        if column in data.columns:
            mask = data[column].astype(str).str.upper().str.startswith("SN", na=False)
            if bool(mask.any()):
                return data.loc[mask].copy()
    if api_name == "fut_holding" and "symbol" in data.columns:
        mask = data["symbol"].astype(str).str.upper().eq("SN")
        if bool(mask.any()):
            return data.loc[mask].copy()
    return data.iloc[0:0].copy()


def _candidate_params(api_name: str, dates: list[str], contracts: list[str]) -> list[dict[str, Any]]:
    latest = dates[0] if dates else datetime.now().strftime("%Y%m%d")
    earliest = dates[-1] if dates else latest
    params: list[dict[str, Any]] = []
    if api_name == "fut_wsr":
        for day in dates or [latest]:
            params.extend(
                [
                    {"symbol": "SN", "trade_date": day},
                    {"symbol": "SN", "trade_date": day, "exchange": "SHFE"},
                    {"symbol": "SN", "trade_date": day, "exchange": "SHF"},
                ]
            )
        params.append({"symbol": "SN", "start_date": earliest, "end_date": latest})
    elif api_name == "fut_settle":
        for contract in contracts:
            for day in dates or [latest]:
                params.append({"ts_code": contract, "trade_date": day})
            params.append({"ts_code": contract, "start_date": earliest, "end_date": latest})
        params.append({"trade_date": latest, "exchange": "SHFE"})
    elif api_name == "fut_holding":
        for day in dates or [latest]:
            params.extend(
                [
                    {"symbol": "SN", "trade_date": day},
                    {"symbol": "SN", "trade_date": day, "exchange": "SHFE"},
                    {"symbol": "SN", "trade_date": day, "exchange": "SHF"},
                ]
            )
        for contract in contracts:
            params.append({"ts_code": contract, "trade_date": latest})
        params.append({"symbol": "SN", "start_date": earliest, "end_date": latest})
    return list({json.dumps(item, sort_keys=True): item for item in params}.values())


def probe_tushare_interface(client: Any, api_name: str, *, max_dates: int = 6) -> ProbeOutcome:
    dates = _market_dates(limit=max_dates)
    contracts = _contract_codes()
    attempts: list[dict[str, Any]] = []
    best_frame = pd.DataFrame()
    best_report: dict[str, Any] | None = None
    first_non_empty_schema_error: dict[str, Any] | None = None

    for params in _candidate_params(api_name, dates, contracts):
        sanitized_params = _sanitize_params(params)
        try:
            frame = _frame_from_call(client, api_name, sanitized_params)
            columns = [str(column) for column in frame.columns]
            schema = validate_required_columns(api_name, columns)
            if not schema["ok"]:
                attempt = {
                    "params_sanitized": sanitized_params,
                    "success": False,
                    "status": "schema_mismatch",
                    "row_count": 0,
                    "columns": columns,
                    "error_message_zh": f"{api_name} returned unexpected columns: missing {', '.join(schema['missing_columns'])}",
                }
                attempts.append(attempt)
                first_non_empty_schema_error = first_non_empty_schema_error or attempt
                continue
            sn_frame = _looks_like_sn(frame, api_name)
            row_count = int(len(sn_frame))
            attempt = {
                "params_sanitized": sanitized_params,
                "success": row_count > 0,
                "status": "success" if row_count > 0 else "no_sn_rows",
                "row_count": row_count,
                "columns": columns,
                "error_message_zh": "" if row_count > 0 else f"{api_name} returned no SN rows for selected params.",
            }
            attempts.append(attempt)
            if row_count > 0 and (best_report is None or row_count > int(best_report.get("row_count") or 0)):
                best_frame = sn_frame
                best_report = attempt
        except Exception as exc:
            status = classify_tushare_error(exc)
            attempts.append(
                {
                    "params_sanitized": sanitized_params,
                    "success": False,
                    "status": status,
                    "row_count": 0,
                    "columns": [],
                    "error_message_zh": sanitize_text(str(exc)),
                }
            )

    selected = best_report or first_non_empty_schema_error or (attempts[0] if attempts else {})
    report = {
        "api_name": api_name,
        "params_sanitized": selected.get("params_sanitized", {}),
        "attempted": bool(attempts),
        "success": bool(best_report),
        "status": "success" if best_report else str(selected.get("status") or "request_failed"),
        "row_count": int(best_report.get("row_count") if best_report else selected.get("row_count") or 0),
        "columns": best_report.get("columns") if best_report else selected.get("columns", []),
        "error_message_zh": "" if best_report else str(selected.get("error_message_zh") or f"{api_name} request failed."),
        "selected_params": best_report.get("params_sanitized") if best_report else {},
        "attempts": attempts,
    }
    return ProbeOutcome(report=sanitize_for_json(report), frame=best_frame.copy())


def build_tushare_param_probe_report(
    *,
    client: Any,
    api_names: Iterable[str] | None = None,
    max_dates: int = 6,
) -> dict[str, Any]:
    names = [str(name) for name in (api_names or ("fut_wsr", "fut_settle", "fut_holding"))]
    results: dict[str, dict[str, Any]] = {}
    for name in names:
        results[name] = probe_tushare_interface(client, name, max_dates=max_dates).report
    payload = {
        "generated_at": _now(),
        "source": "tushare",
        "status": "success" if all(item.get("success") for item in results.values()) else "partial_success" if any(item.get("success") for item in results.values()) else "failed",
        "success": all(item.get("success") for item in results.values()) if results else False,
        "results": results,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    _write_json(_fundamentals_dir() / "tushare_param_probe_report.json", payload)
    return sanitize_for_json(payload)
