from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import numpy as np
import pandas as pd


@dataclass
class DataQualityReport:
    missing_rate: float
    duplicate_count: int
    stale_data_flag: bool
    outlier_count: int
    source_consistency_score: float
    last_valid_timestamp: str
    last_valid_price: float | None
    price_jump_flags: int
    volume_anomaly_flags: int
    open_interest_anomaly_flags: int
    ohlc_error_count: int
    quality_score: float
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_data_quality_report(
    frame: pd.DataFrame | None,
    *,
    timestamp_col: str | None = None,
    now: pd.Timestamp | None = None,
    max_stale_hours: float = 36.0,
    source_consistency_score: float = 1.0,
) -> DataQualityReport:
    if frame is None or frame.empty:
        return DataQualityReport(
            missing_rate=1.0,
            duplicate_count=0,
            stale_data_flag=True,
            outlier_count=0,
            source_consistency_score=0.0,
            last_valid_timestamp="",
            last_valid_price=None,
            price_jump_flags=0,
            volume_anomaly_flags=0,
            open_interest_anomaly_flags=0,
            ohlc_error_count=0,
            quality_score=0.0,
            summary="无可用行情数据，禁止生成实盘预测。",
        )

    work = frame.copy()
    price_cols = [col for col in ("open", "high", "low", "close") if col in work.columns]
    numeric_cols = price_cols + [col for col in ("volume", "open_interest") if col in work.columns]
    for col in numeric_cols:
        work[col] = pd.to_numeric(work[col], errors="coerce")

    missing_rate = float(work[numeric_cols].isna().mean().mean()) if numeric_cols else 1.0
    idx = pd.to_datetime(work[timestamp_col], errors="coerce") if timestamp_col and timestamp_col in work.columns else pd.to_datetime(work.index, errors="coerce")
    duplicate_count = int(idx.duplicated().sum()) if len(idx) else 0
    close = work["close"].dropna() if "close" in work.columns else pd.Series(dtype=float)
    last_valid_price = float(close.iloc[-1]) if not close.empty and np.isfinite(close.iloc[-1]) else None
    last_ts = idx.dropna().max() if len(idx) else pd.NaT
    if pd.isna(last_ts):
        last_ts_text = ""
        stale = True
    else:
        if last_ts.tzinfo is None:
            last_ts = last_ts.tz_localize("Asia/Hong_Kong")
        else:
            last_ts = last_ts.tz_convert("Asia/Hong_Kong")
        now_ts = now or pd.Timestamp.now(tz="Asia/Hong_Kong")
        if now_ts.tzinfo is None:
            now_ts = now_ts.tz_localize("Asia/Hong_Kong")
        stale = (now_ts - last_ts).total_seconds() / 3600.0 > max_stale_hours
        last_ts_text = last_ts.isoformat()

    ohlc_errors = 0
    if {"open", "high", "low", "close"}.issubset(work.columns):
        ohlc_errors = int(((work["high"] < work[["open", "close"]].max(axis=1)) | (work["low"] > work[["open", "close"]].min(axis=1))).fillna(False).sum())

    returns = close.pct_change().replace([np.inf, -np.inf], np.nan).dropna()
    price_jump_flags = int((returns.abs() > max(returns.std() * 6.0, 0.08)).sum()) if not returns.empty else 0
    outlier_count = price_jump_flags + ohlc_errors
    volume_anomaly = 0
    if "volume" in work.columns:
        volume = work["volume"].dropna()
        volume_anomaly = int((volume < 0).sum())
        if len(volume) > 20:
            volume_anomaly += int(((volume - volume.rolling(20).median()).abs() > volume.rolling(20).std().fillna(0) * 8).fillna(False).sum())
    oi_anomaly = 0
    if "open_interest" in work.columns:
        oi = work["open_interest"].dropna()
        oi_anomaly = int((oi < 0).sum())

    penalty = (
        min(missing_rate, 1.0) * 0.35
        + min(duplicate_count / max(len(work), 1), 1.0) * 0.12
        + (0.20 if stale else 0.0)
        + min(outlier_count / max(len(work), 1), 1.0) * 0.18
        + min((volume_anomaly + oi_anomaly) / max(len(work), 1), 1.0) * 0.10
        + (1.0 - max(0.0, min(source_consistency_score, 1.0))) * 0.20
    )
    quality = float(max(0.0, min(1.0, 1.0 - penalty)))
    summary = "数据质量可用"
    if quality < 0.55:
        summary = "数据质量偏低，预测应降权或仅展示参考区间"
    if stale:
        summary += "；行情时间可能滞后"
    if ohlc_errors:
        summary += f"；发现 {ohlc_errors} 条 OHLC 逻辑异常"

    return DataQualityReport(
        missing_rate=round(missing_rate, 6),
        duplicate_count=duplicate_count,
        stale_data_flag=bool(stale),
        outlier_count=int(outlier_count),
        source_consistency_score=round(float(source_consistency_score), 6),
        last_valid_timestamp=last_ts_text,
        last_valid_price=last_valid_price,
        price_jump_flags=price_jump_flags,
        volume_anomaly_flags=volume_anomaly,
        open_interest_anomaly_flags=oi_anomaly,
        ohlc_error_count=ohlc_errors,
        quality_score=round(quality, 6),
        summary=summary,
    )
