from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class FactorSpec:
    feature_name: str
    group: str
    direction_hint: str
    required_columns: tuple[str, ...]
    description_zh: str
    lookback_window: int

    def to_dict(self) -> dict[str, object]:
        payload = asdict(self)
        payload["required_columns"] = list(self.required_columns)
        return payload


@dataclass
class FactorBuildResult:
    frame: pd.DataFrame
    metadata: list[FactorSpec]
    missing: dict[str, str]

    def __iter__(self):
        yield self.frame
        yield self.metadata
        yield self.missing


def numeric(frame: pd.DataFrame, column: str, *, default: float = np.nan) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(default, index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce")


def missing_required(frame: pd.DataFrame, required: Iterable[str]) -> list[str]:
    return [column for column in required if column not in frame.columns]


def rolling_zscore(series: pd.Series, window: int, *, min_periods: int | None = None) -> pd.Series:
    min_periods = min_periods or max(5, window // 4)
    mean = series.rolling(window, min_periods=min_periods).mean()
    std = series.rolling(window, min_periods=min_periods).std().replace(0, np.nan)
    return (series - mean) / std


def true_range(frame: pd.DataFrame) -> pd.Series:
    high = numeric(frame, "high")
    low = numeric(frame, "low")
    close = numeric(frame, "close")
    prev_close = close.shift(1)
    return pd.concat([(high - low).abs(), (high - prev_close).abs(), (low - prev_close).abs()], axis=1).max(axis=1)


def percentile_rank(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window, min_periods=max(10, window // 5)).rank(pct=True)


def finish(frame: pd.DataFrame, metadata: list[FactorSpec], missing: dict[str, str]) -> FactorBuildResult:
    return FactorBuildResult(frame=frame.replace([np.inf, -np.inf], np.nan), metadata=metadata, missing=missing)
