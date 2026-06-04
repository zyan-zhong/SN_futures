from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd


COST_FEATURES = (
    "settlement_basis_to_close",
    "settlement_return",
    "trading_fee_rate",
    "fee_rate",
    "trading_fee_level",
    "long_margin_rate",
    "short_margin_rate",
    "margin_spread",
    "offset_today_fee",
    "intraday_cost",
    "cost_pressure_score",
)
POSITIONING_FEATURES = (
    "member_net_position",
    "member_net_position_change",
    "member_long_short_ratio",
    "member_position_available_flag",
    "member_position_event_score",
    "top_member_direction_score",
)
SPARSE_FEATURES = (
    "member_net_position",
    "member_net_position_change",
    "member_long_short_ratio",
)
SPARSE_POLICY = {
    "raw_missing_fill": "preserve_nan",
    "neutral_features": ["member_position_event_score", "top_member_direction_score"],
    "availability_flag": "member_position_available_flag",
    "no_future_backfill": True,
    "sparse_decay": "disabled",
}


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _rows(payload: Any) -> list[Mapping[str, Any]]:
    if isinstance(payload, Mapping):
        if payload.get("sample") or payload.get("sample_mode") or payload.get("sample_data_used") or payload.get("mock_data_used"):
            return []
        rows = payload.get("rows") or payload.get("data") or payload.get("history") or []
    elif isinstance(payload, list):
        rows = payload
    else:
        rows = []
    return [row for row in rows if isinstance(row, Mapping) and not row.get("sample") and not row.get("mock_data_used")]


def _frame_from_rows(rows: list[Mapping[str, Any]]) -> pd.DataFrame:
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    date_col = "trade_date" if "trade_date" in frame.columns else "date" if "date" in frame.columns else None
    if date_col is None:
        return pd.DataFrame()
    frame.index = pd.DatetimeIndex(pd.to_datetime(frame[date_col], errors="coerce")).normalize()
    frame = frame[~frame.index.isna()].sort_index()
    if frame.empty:
        return pd.DataFrame()
    return frame


def _numeric_column(frame: pd.DataFrame, *names: str) -> pd.Series:
    for name in names:
        if name in frame.columns:
            return pd.to_numeric(frame[name], errors="coerce")
    return pd.Series(np.nan, index=frame.index, dtype="float64")


def _align_last(frame: pd.DataFrame, target_index: pd.DatetimeIndex, aliases: Mapping[str, tuple[str, ...]]) -> pd.DataFrame:
    out = pd.DataFrame(index=target_index)
    if frame.empty:
        for target in aliases:
            out[target] = np.nan
        return out
    grouped = frame.groupby(frame.index).last()
    for target, names in aliases.items():
        out[target] = _numeric_column(grouped, *names).reindex(target_index)
    return out


def _align_settlement_features(market: pd.DataFrame, output_dir: Path, target_index: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict[str, Any]]:
    fundamentals = output_dir / "fundamentals"
    daily = _frame_from_rows(_rows(_read_json(fundamentals / "sn_tushare_daily.json")))
    settlement = _frame_from_rows(_rows(_read_json(fundamentals / "sn_tushare_settlement.json")))
    daily_aligned = _align_last(
        daily,
        target_index,
        {
            "open_interest": ("open_interest", "oi"),
            "daily_settlement": ("settlement", "settle"),
        },
    )
    settle_aligned = _align_last(
        settlement,
        target_index,
        {
            "settlement": ("settlement", "settle"),
            "trading_fee": ("trading_fee", "trade_fee"),
            "trading_fee_rate": ("trading_fee_rate", "trade_fee_rate"),
            "long_margin_rate": ("long_margin_rate",),
            "short_margin_rate": ("short_margin_rate",),
            "offset_today_fee": ("offset_today_fee",),
        },
    )
    frame = pd.DataFrame(index=target_index)
    frame["open_interest"] = daily_aligned["open_interest"]
    settlement_series = pd.to_numeric(settle_aligned["settlement"], errors="coerce")
    daily_settlement = pd.to_numeric(daily_aligned["daily_settlement"], errors="coerce")
    frame["settlement"] = settlement_series.where(settlement_series.notna(), daily_settlement)
    for field in ("trading_fee", "trading_fee_rate", "long_margin_rate", "short_margin_rate", "offset_today_fee"):
        frame[field] = settle_aligned[field]

    # Settlement and fee parameters are public same-day records. Forward-fill
    # only from past observations so sparse official updates can still describe
    # current cost regime without future leakage.
    for field in ("settlement", "trading_fee", "trading_fee_rate", "long_margin_rate", "short_margin_rate", "offset_today_fee"):
        frame[field] = pd.to_numeric(frame[field], errors="coerce").ffill()

    close = pd.to_numeric(market.get("close", pd.Series(np.nan, index=target_index)), errors="coerce").reindex(target_index)
    settlement_value = pd.to_numeric(frame["settlement"], errors="coerce")
    trading_fee = pd.to_numeric(frame["trading_fee"], errors="coerce")
    fee_rate = pd.to_numeric(frame["trading_fee_rate"], errors="coerce")
    fee_rate = fee_rate.combine_first(trading_fee / settlement_value.replace(0, np.nan))
    long_margin = pd.to_numeric(frame["long_margin_rate"], errors="coerce")
    short_margin = pd.to_numeric(frame["short_margin_rate"], errors="coerce")
    offset_today_fee = pd.to_numeric(frame["offset_today_fee"], errors="coerce")

    frame["settlement_basis_to_close"] = settlement_value - close
    frame["settlement_return"] = settlement_value.pct_change(fill_method=None)
    frame["fee_rate"] = fee_rate
    frame["trading_fee_level"] = trading_fee
    frame["margin_spread"] = short_margin - long_margin
    frame["intraday_cost"] = offset_today_fee
    frame["cost_pressure_score"] = (
        fee_rate.fillna(0.0) * 10000.0
        + ((long_margin + short_margin) / 2.0).fillna(0.0) * 100.0
        + (offset_today_fee / settlement_value.replace(0, np.nan)).fillna(0.0) * 10000.0
    )
    return frame, {
        "daily_row_count": int(len(daily)),
        "settlement_row_count": int(len(settlement)),
        "daily_used": bool(len(daily) > 0 and frame["open_interest"].notna().any()),
        "settle_used": bool(len(settlement) > 0 and any(frame[field].notna().any() for field in ("trading_fee_rate", "long_margin_rate", "short_margin_rate", "offset_today_fee"))),
    }


def _align_holding_features(output_dir: Path, target_index: pd.DatetimeIndex) -> tuple[pd.DataFrame, dict[str, Any]]:
    holding = _frame_from_rows(_rows(_read_json(output_dir / "fundamentals" / "sn_tushare_holding.json")))
    out = pd.DataFrame(index=target_index)
    for field in POSITIONING_FEATURES:
        out[field] = np.nan
    if holding.empty:
        out["member_position_available_flag"] = 0.0
        out["member_position_event_score"] = 0.0
        out["top_member_direction_score"] = 0.0
        return out, {"holding_row_count": 0, "holding_used": False}

    normalized = pd.DataFrame(index=holding.index)
    normalized["long_position"] = _numeric_column(holding, "long_position", "long_hld", "long")
    normalized["short_position"] = _numeric_column(holding, "short_position", "short_hld", "short")
    normalized["long_change"] = _numeric_column(holding, "long_change", "long_chg")
    normalized["short_change"] = _numeric_column(holding, "short_change", "short_chg")
    explicit_net = _numeric_column(holding, "member_net_position", "net_position")
    grouped = normalized.groupby(normalized.index).sum(min_count=1)
    explicit_grouped = explicit_net.groupby(explicit_net.index).sum(min_count=1)
    derived_net = grouped["long_position"] - grouped["short_position"]
    net = explicit_grouped.where(explicit_grouped.notna(), derived_net)
    denom = (grouped["long_position"] + grouped["short_position"]).replace(0, np.nan)
    ratio = grouped["long_position"] / grouped["short_position"].replace(0, np.nan)
    direction = (net / denom).clip(-1.0, 1.0)
    change = net.diff()

    out["member_net_position"] = net.reindex(target_index)
    out["member_net_position_change"] = change.reindex(target_index)
    out["member_long_short_ratio"] = ratio.reindex(target_index)
    out["member_position_available_flag"] = out["member_net_position"].notna().astype(float)
    out["member_position_event_score"] = direction.reindex(target_index).fillna(0.0)
    out["top_member_direction_score"] = direction.reindex(target_index).fillna(0.0)
    return out, {
        "holding_row_count": int(len(holding)),
        "holding_used": bool(out["member_position_available_flag"].sum() > 0),
        "observed_trade_dates": int(out["member_position_available_flag"].sum()),
    }


def build_tushare_v7_feature_frame(market: pd.DataFrame, output_dir: Path) -> tuple[pd.DataFrame, dict[str, Any]]:
    if market.empty or "trade_date" not in market.columns:
        return pd.DataFrame(), {
            "status": "missing_market",
            "cost_features": list(COST_FEATURES),
            "positioning_features": list(POSITIONING_FEATURES),
            "sparse_features": list(SPARSE_FEATURES),
            "sparse_policy": dict(SPARSE_POLICY),
        }
    target_index = pd.DatetimeIndex(pd.to_datetime(market["trade_date"], errors="coerce")).normalize()
    market_aligned = market.copy()
    market_aligned.index = target_index
    settlement_frame, settlement_diag = _align_settlement_features(market_aligned, output_dir, target_index)
    holding_frame, holding_diag = _align_holding_features(output_dir, target_index)
    frame = pd.concat([settlement_frame, holding_frame], axis=1)
    frame["trade_date"] = target_index.strftime("%Y-%m-%d")
    diagnostics = {
        "status": "success",
        "cost_features": list(COST_FEATURES),
        "positioning_features": list(POSITIONING_FEATURES),
        "sparse_features": list(SPARSE_FEATURES),
        "sparse_policy": dict(SPARSE_POLICY),
        **settlement_diag,
        **holding_diag,
    }
    return frame, diagnostics
