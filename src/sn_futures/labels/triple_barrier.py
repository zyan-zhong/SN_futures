from __future__ import annotations

from typing import Literal

import numpy as np
import pandas as pd


TradeSide = Literal["long", "short"]


def _true_range(frame: pd.DataFrame) -> pd.Series:
    close = pd.to_numeric(frame["close"], errors="coerce")
    if {"high", "low"}.issubset(frame.columns):
        high = pd.to_numeric(frame["high"], errors="coerce")
        low = pd.to_numeric(frame["low"], errors="coerce")
        prev_close = close.shift(1)
        return pd.concat(
            [
                (high - low).abs(),
                (high - prev_close).abs(),
                (low - prev_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
    return close.diff().abs()


def _atr(frame: pd.DataFrame, atr_col: str, window: int = 14) -> pd.Series:
    if atr_col in frame.columns:
        atr = pd.to_numeric(frame[atr_col], errors="coerce")
    else:
        atr = _true_range(frame).rolling(window, min_periods=1).mean()
    fallback = _true_range(frame).expanding(min_periods=1).median()
    return atr.fillna(fallback).replace(0, np.nan)


def add_triple_barrier_labels(
    frame: pd.DataFrame,
    *,
    horizon: int = 5,
    k_up: float = 1.0,
    k_down: float = 1.0,
    side: TradeSide = "long",
    conservative: bool = True,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    atr_col: str = "atr_14",
) -> pd.DataFrame:
    """Apply side-aware triple-barrier labels.

    ``tb_label`` is side-adjusted: +1 means the target/profit barrier was hit,
    -1 means the stop/loss barrier was hit, and 0 means only the vertical
    barrier was reached.  With ``side="short"``, a lower price barrier is the
    favorable target.
    """

    if horizon <= 0:
        raise ValueError("horizon must be a positive integer.")
    if side not in {"long", "short"}:
        raise ValueError("side must be 'long' or 'short'.")
    if price_col not in frame.columns:
        raise KeyError(f"Missing required price column: {price_col}")

    out = frame.copy()
    close = pd.to_numeric(out[price_col], errors="coerce")
    high = pd.to_numeric(out[high_col], errors="coerce") if high_col in out.columns else close
    low = pd.to_numeric(out[low_col], errors="coerce") if low_col in out.columns else close
    atr = _atr(out, atr_col)

    upper = close + float(k_up) * atr
    lower = close - float(k_down) * atr

    labels: list[int | pd._libs.missing.NAType] = []
    hit_times: list[object] = []
    hit_prices: list[float] = []
    horizons: list[int | pd._libs.missing.NAType] = []

    index_values = list(out.index)
    for pos in range(len(out)):
        if pos + horizon >= len(out) or not np.isfinite(close.iloc[pos]) or not np.isfinite(atr.iloc[pos]):
            labels.append(pd.NA)
            hit_times.append(pd.NA)
            hit_prices.append(np.nan)
            horizons.append(pd.NA)
            continue

        upper_barrier = float(upper.iloc[pos])
        lower_barrier = float(lower.iloc[pos])
        label = 0
        hit_time: object = index_values[pos + horizon]
        hit_price = float(close.iloc[pos + horizon])
        hit_offset = horizon

        for step in range(1, horizon + 1):
            row_high = float(high.iloc[pos + step]) if np.isfinite(high.iloc[pos + step]) else float(close.iloc[pos + step])
            row_low = float(low.iloc[pos + step]) if np.isfinite(low.iloc[pos + step]) else float(close.iloc[pos + step])
            hit_upper = row_high >= upper_barrier
            hit_lower = row_low <= lower_barrier
            if not hit_upper and not hit_lower:
                continue

            if hit_upper and hit_lower:
                if conservative:
                    label = -1
                    hit_price = upper_barrier if side == "short" else lower_barrier
                else:
                    label = 1
                    hit_price = lower_barrier if side == "short" else upper_barrier
            elif side == "long":
                label = 1 if hit_upper else -1
                hit_price = upper_barrier if hit_upper else lower_barrier
            else:
                label = 1 if hit_lower else -1
                hit_price = lower_barrier if hit_lower else upper_barrier
            hit_time = index_values[pos + step]
            hit_offset = step
            break

        labels.append(label)
        hit_times.append(hit_time)
        hit_prices.append(hit_price)
        horizons.append(hit_offset)

    out["tb_label"] = pd.Series(labels, index=out.index, dtype="Int64")
    out["tb_hit_time"] = hit_times
    out["tb_hit_price"] = hit_prices
    out["tb_horizon"] = pd.Series(horizons, index=out.index, dtype="Int64")
    out["tb_upper"] = upper
    out["tb_lower"] = lower
    return out

