from __future__ import annotations

from collections.abc import Iterable
from typing import Any

import numpy as np
import pandas as pd


DEFAULT_FORWARD_HORIZONS = (1, 3, 5, 10, 20)


def _future_window(frame: pd.Series, horizon: int) -> pd.DataFrame:
    return pd.concat([frame.shift(-step) for step in range(1, horizon + 1)], axis=1)


def _direction(ret: pd.Series, threshold: float) -> pd.Series:
    values = np.select([ret > threshold, ret < -threshold], [1, -1], default=0)
    out = pd.Series(values, index=ret.index, dtype="Int64")
    out[ret.isna()] = pd.NA
    return out


def forward_label_columns(horizons: Iterable[int] = DEFAULT_FORWARD_HORIZONS) -> list[str]:
    columns: list[str] = []
    for horizon in horizons:
        suffix = f"{int(horizon)}d"
        columns.extend(
            [
                f"ret_{suffix}",
                f"direction_{suffix}",
                f"abs_ret_{suffix}",
                f"realized_vol_{suffix}",
                f"max_favorable_excursion_{suffix}",
                f"max_adverse_excursion_{suffix}",
            ]
        )
    return columns


def add_forward_return_labels(
    frame: pd.DataFrame,
    *,
    horizons: Iterable[int] = DEFAULT_FORWARD_HORIZONS,
    price_col: str = "close",
    high_col: str = "high",
    low_col: str = "low",
    direction_threshold: float | dict[int, float] = 0.0,
) -> pd.DataFrame:
    """Add causal forward-return labels.

    The labels intentionally use future ``shift(-horizon)`` values and are
    therefore targets only.  Downstream training code must remove the returned
    label columns from feature matrices; use ``forward_label_columns`` or the
    leakage guard helpers for that.
    """

    if price_col not in frame.columns:
        raise KeyError(f"Missing required price column: {price_col}")

    out = frame.copy()
    close = pd.to_numeric(out[price_col], errors="coerce")
    high = pd.to_numeric(out[high_col], errors="coerce") if high_col in out.columns else close
    low = pd.to_numeric(out[low_col], errors="coerce") if low_col in out.columns else close
    one_step_returns = close.pct_change(fill_method=None)

    for raw_horizon in horizons:
        horizon = int(raw_horizon)
        if horizon <= 0:
            raise ValueError("Forward label horizons must be positive integers.")
        suffix = f"{horizon}d"
        future_close = close.shift(-horizon)
        ret = future_close / close - 1.0
        threshold = (
            float(direction_threshold.get(horizon, 0.0))
            if isinstance(direction_threshold, dict)
            else float(direction_threshold)
        )

        future_high = _future_window(high, horizon).max(axis=1, skipna=True)
        future_low = _future_window(low, horizon).min(axis=1, skipna=True)
        future_vol = _future_window(one_step_returns, horizon).std(axis=1, skipna=True)

        insufficient_tail = future_close.isna()
        future_high[insufficient_tail] = np.nan
        future_low[insufficient_tail] = np.nan
        future_vol[insufficient_tail] = np.nan

        out[f"ret_{suffix}"] = ret
        out[f"direction_{suffix}"] = _direction(ret, threshold)
        out[f"abs_ret_{suffix}"] = ret.abs()
        out[f"realized_vol_{suffix}"] = future_vol
        out[f"max_favorable_excursion_{suffix}"] = future_high / close - 1.0
        out[f"max_adverse_excursion_{suffix}"] = future_low / close - 1.0
    return out


def remove_forward_labels_from_features(
    frame: pd.DataFrame,
    *,
    horizons: Iterable[int] = DEFAULT_FORWARD_HORIZONS,
    extra_label_columns: Iterable[str] | None = None,
) -> pd.DataFrame:
    labels = set(forward_label_columns(horizons))
    labels.update(str(col) for col in (extra_label_columns or []))
    return frame.drop(columns=[col for col in labels if col in frame.columns])

