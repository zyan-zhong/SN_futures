from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


CROSS_MARKET_VALUE_FIELDS = (
    "usd_cny",
    "usd_cny_return",
    "us10y",
    "us10y_change",
    "copper_global_proxy",
    "copper_global_proxy_return",
    "copper_proxy_return",
)
MAX_FORWARD_FILL_TRADING_DAYS = 5


def _fundamentals_dir(output_dir: Path | None = None) -> Path:
    return (output_dir or get_user_output_dir()) / "fundamentals"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _rows_from_payload(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        if payload.get("sample") or payload.get("sample_mode"):
            return []
        rows = payload.get("rows") or payload.get("data") or payload.get("history") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [row for row in rows if isinstance(row, Mapping) and not row.get("sample")]


def _status_payload(output_dir: Path | None = None) -> Mapping[str, Any]:
    payload = _read_json(_fundamentals_dir(output_dir) / "fx_macro_provider_status.json")
    return payload if isinstance(payload, Mapping) else {}


def _date_col(frame: pd.DataFrame) -> str | None:
    for column in ("trade_date", "date", "time", "timestamp"):
        if column in frame.columns:
            return column
    return None


def _empty_diagnostics(reason: str, source_path: Path | None = None) -> dict[str, Any]:
    return {
        "source_path": str(source_path or ""),
        "raw_row_count": 0,
        "normalized_row_count": 0,
        "date_start": None,
        "date_end": None,
        "market_date_start": None,
        "market_date_end": None,
        "exact_date_overlap_count": 0,
        "aligned_non_null_count": 0,
        "stale_row_count": 0,
        "max_forward_fill_trading_days": MAX_FORWARD_FILL_TRADING_DAYS,
        "fields": list(CROSS_MARKET_VALUE_FIELDS),
        "field_diagnostics": {},
        "blocking_reasons": [reason],
        "lme_tin_close_status": "unavailable",
        "message_zh": "跨市场数据暂不可用；系统不会伪造字段。",
    }


def load_cross_market_frame(output_dir: Path | None = None) -> tuple[pd.DataFrame, dict[str, Any]]:
    path = _fundamentals_dir(output_dir) / "sn_cross_market.json"
    payload = _read_json(path)
    if payload is None:
        return pd.DataFrame(), _empty_diagnostics("no_file", path)
    rows = _rows_from_payload(payload)
    if not rows:
        return pd.DataFrame(), _empty_diagnostics("empty_file", path)
    frame = pd.DataFrame(rows)
    normalized = normalize_cross_market_dates(frame)
    diagnostics = {
        "source_path": str(path),
        "raw_row_count": int(len(rows)),
        "normalized_row_count": int(len(normalized)),
        "date_start": normalized.index.min().isoformat() if not normalized.empty else None,
        "date_end": normalized.index.max().isoformat() if not normalized.empty else None,
        "fields": [field for field in CROSS_MARKET_VALUE_FIELDS if field in normalized.columns],
        "blocking_reasons": [] if not normalized.empty else ["empty_file"],
        "lme_tin_close_status": "unavailable",
    }
    return normalized, diagnostics


def normalize_cross_market_dates(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    date_col = _date_col(frame)
    if date_col is None:
        return pd.DataFrame()
    out = frame.copy()
    parsed_dates = pd.to_datetime(out[date_col], errors="coerce")
    out.index = pd.DatetimeIndex(parsed_dates).normalize()
    out = out[~out.index.isna()].sort_index()
    out = out[~out.index.duplicated(keep="last")]
    for column in CROSS_MARKET_VALUE_FIELDS:
        if column in out.columns:
            out[column] = pd.to_numeric(out[column], errors="coerce")
    if "usd_cny" in out.columns and "usd_cny_return" not in out.columns:
        out["usd_cny_return"] = out["usd_cny"].pct_change(1, fill_method=None)
    if "us10y" in out.columns and "us10y_change" not in out.columns:
        out["us10y_change"] = out["us10y"].diff(1)
    if "copper_global_proxy" in out.columns:
        if "copper_global_proxy_return" not in out.columns:
            out["copper_global_proxy_return"] = out["copper_global_proxy"].pct_change(1, fill_method=None)
        if "copper_proxy_return" not in out.columns:
            out["copper_proxy_return"] = out["copper_global_proxy_return"]
    keep = [column for column in CROSS_MARKET_VALUE_FIELDS if column in out.columns]
    return out[keep]


def _market_dates(market_frame: pd.DataFrame) -> pd.DatetimeIndex:
    if len(market_frame.index) == 0:
        return pd.DatetimeIndex([])
    values = pd.to_datetime(market_frame.index, errors="coerce")
    values = pd.DatetimeIndex(values).dropna().normalize()
    return pd.DatetimeIndex(sorted(values.unique()))


def align_cross_market_to_market_history(
    market_frame: pd.DataFrame,
    cross_frame: pd.DataFrame,
    *,
    max_forward_fill_trading_days: int = MAX_FORWARD_FILL_TRADING_DAYS,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    market_dates = _market_dates(market_frame)
    if market_dates.empty:
        return pd.DataFrame(), _empty_diagnostics("empty_market_history")
    if cross_frame.empty:
        diagnostics = _empty_diagnostics("empty_file")
        diagnostics.update(
            {
                "market_date_start": market_dates.min().isoformat(),
                "market_date_end": market_dates.max().isoformat(),
            }
        )
        return pd.DataFrame(index=market_dates), diagnostics

    cross = cross_frame.sort_index()
    cross_dates = pd.DatetimeIndex(cross.index).normalize()
    fields = [field for field in CROSS_MARKET_VALUE_FIELDS if field in cross.columns]
    aligned = pd.DataFrame(index=market_dates)
    stale_mask = pd.Series(False, index=market_dates)
    last_source_dates: list[str | None] = []

    for pos, date in enumerate(market_dates):
        idx = cross_dates.searchsorted(date, side="right") - 1
        if idx < 0:
            last_source_dates.append(None)
            continue
        source_date = cross_dates[idx]
        previous_market_pos = market_dates.searchsorted(source_date, side="right") - 1
        if previous_market_pos < 0:
            age = int(np.busday_count(source_date.date(), date.date()))
        else:
            age = pos - previous_market_pos
        last_source_dates.append(source_date.isoformat())
        if age > max_forward_fill_trading_days:
            stale_mask.loc[date] = True
            continue
        for field in fields:
            aligned.loc[date, field] = cross.iloc[idx].get(field)

    # Keep both old and explicit copper return names for backward compatibility.
    if "copper_global_proxy_return" in aligned.columns and "copper_proxy_return" not in aligned.columns:
        aligned["copper_proxy_return"] = aligned["copper_global_proxy_return"]
    if "copper_proxy_return" in aligned.columns and "copper_global_proxy_return" not in aligned.columns:
        aligned["copper_global_proxy_return"] = aligned["copper_proxy_return"]

    exact_overlap = len(set(market_dates).intersection(set(cross_dates)))
    field_diagnostics: dict[str, dict[str, Any]] = {}
    aligned_non_null_count = 0
    for field in [field for field in CROSS_MARKET_VALUE_FIELDS if field in aligned.columns]:
        series = pd.to_numeric(aligned[field], errors="coerce")
        non_null = int(series.notna().sum())
        aligned_non_null_count += non_null
        field_diagnostics[field] = {
            "non_null_count": non_null,
            "non_null_rate": round(non_null / max(len(market_dates), 1), 6),
            "status": "available" if non_null else "unavailable",
        }

    blocking: list[str] = []
    status_payload = _status_payload()
    status = str(status_payload.get("status") or status_payload.get("alpha_vantage_status") or "")
    if status in {"key_missing", "rate_limited", "key_invalid", "network_failed"}:
        blocking.append(status)
    if aligned_non_null_count <= 0:
        blocking.append("no_date_overlap" if exact_overlap == 0 else "stale_after_alignment")
    elif any(row["non_null_rate"] < 0.7 for row in field_diagnostics.values()):
        blocking.append("insufficient_non_null_rate")
    if int(stale_mask.sum()) > 0:
        blocking.append("stale_after_alignment")

    diagnostics = {
        "raw_row_count": int(len(cross_frame)),
        "normalized_row_count": int(len(cross_frame)),
        "date_start": cross_dates.min().isoformat() if len(cross_dates) else None,
        "date_end": cross_dates.max().isoformat() if len(cross_dates) else None,
        "market_date_start": market_dates.min().isoformat(),
        "market_date_end": market_dates.max().isoformat(),
        "exact_date_overlap_count": int(exact_overlap),
        "aligned_non_null_count": int(aligned_non_null_count),
        "stale_row_count": int(stale_mask.sum()),
        "max_forward_fill_trading_days": int(max_forward_fill_trading_days),
        "fields": [field for field in CROSS_MARKET_VALUE_FIELDS if field in aligned.columns],
        "field_diagnostics": field_diagnostics,
        "blocking_reasons": sorted(set(blocking)),
        "last_source_dates": last_source_dates,
        "lme_tin_close_status": "unavailable",
        "message_zh": "跨市场数据已按沪锡交易日对齐；超过 5 个交易日的 forward-fill 会标记为 stale。",
    }
    aligned["_cross_market_stale"] = stale_mask.astype(bool)
    return aligned, sanitize_for_json(diagnostics)


def build_cross_market_feature_frame(
    market_frame: pd.DataFrame,
    *,
    output_dir: Path | None = None,
    max_forward_fill_trading_days: int = MAX_FORWARD_FILL_TRADING_DAYS,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    cross, load_diagnostics = load_cross_market_frame(output_dir)
    if cross.empty:
        market_dates = _market_dates(market_frame)
        empty = pd.DataFrame(index=market_dates)
        diagnostics = dict(load_diagnostics)
        diagnostics.update(
            {
                "market_date_start": market_dates.min().isoformat() if len(market_dates) else None,
                "market_date_end": market_dates.max().isoformat() if len(market_dates) else None,
            }
        )
        return empty, sanitize_for_json(diagnostics)
    aligned, diagnostics = align_cross_market_to_market_history(
        market_frame,
        cross,
        max_forward_fill_trading_days=max_forward_fill_trading_days,
    )
    diagnostics.update({key: value for key, value in load_diagnostics.items() if key not in diagnostics})
    diagnostics["generated_at"] = datetime.now().isoformat(timespec="seconds")
    return aligned, sanitize_for_json(diagnostics)


def write_cross_market_alignment_audit(output_dir: Path | None = None) -> dict[str, Any]:
    output = output_dir or get_user_output_dir()
    history_payload = _read_json(output / "sn_market_history.json")
    rows = _rows_from_payload(history_payload)
    market = pd.DataFrame(rows)
    if not market.empty:
        date_col = _date_col(market) or "time"
        market.index = pd.to_datetime(market[date_col], errors="coerce")
        market = market[~market.index.isna()]
    aligned, diagnostics = build_cross_market_feature_frame(market, output_dir=output)
    payload = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "diagnostics": diagnostics,
        "aligned_columns": list(aligned.columns),
        "aligned_row_count": int(len(aligned)),
    }
    path = output / "fundamentals" / "cross_market_alignment_diagnostics.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return sanitize_for_json(payload)
