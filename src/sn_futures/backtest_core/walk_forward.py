from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import pandas as pd

from .engine import BacktestConfig, run_futures_backtest


@dataclass(frozen=True)
class WalkForwardWindow:
    train_start: pd.Timestamp
    train_end: pd.Timestamp
    validation_start: pd.Timestamp
    validation_end: pd.Timestamp
    test_start: pd.Timestamp
    test_end: pd.Timestamp

    def as_dict(self) -> dict[str, str]:
        return {
            "train_start": self.train_start.isoformat(),
            "train_end": self.train_end.isoformat(),
            "validation_start": self.validation_start.isoformat(),
            "validation_end": self.validation_end.isoformat(),
            "test_start": self.test_start.isoformat(),
            "test_end": self.test_end.isoformat(),
        }


def _normalise_index(index: Iterable[object]) -> pd.DatetimeIndex:
    dt_index = pd.DatetimeIndex(pd.to_datetime(list(index), errors="coerce")).dropna().sort_values().unique()
    if len(dt_index) == 0:
        return pd.DatetimeIndex([])
    return pd.DatetimeIndex(dt_index)


def build_walk_forward_windows(
    index: Iterable[object],
    *,
    train_window: int,
    validation_window: int,
    test_window: int,
    step: int | None = None,
) -> list[WalkForwardWindow]:
    """Build strictly ordered walk-forward windows from an existing time index.

    Window arguments are row counts. This keeps the helper independent from
    bar frequency and avoids calendar guesses that could introduce look-ahead.
    """

    dt_index = _normalise_index(index)
    if train_window <= 0 or validation_window <= 0 or test_window <= 0:
        raise ValueError("train_window, validation_window and test_window must be positive")
    step = int(step or test_window)
    if step <= 0:
        raise ValueError("step must be positive")

    windows: list[WalkForwardWindow] = []
    start = 0
    total = train_window + validation_window + test_window
    while start + total <= len(dt_index):
        train_slice = dt_index[start : start + train_window]
        validation_slice = dt_index[start + train_window : start + train_window + validation_window]
        test_slice = dt_index[start + train_window + validation_window : start + total]
        windows.append(
            WalkForwardWindow(
                train_start=pd.Timestamp(train_slice[0]),
                train_end=pd.Timestamp(train_slice[-1]),
                validation_start=pd.Timestamp(validation_slice[0]),
                validation_end=pd.Timestamp(validation_slice[-1]),
                test_start=pd.Timestamp(test_slice[0]),
                test_end=pd.Timestamp(test_slice[-1]),
            )
        )
        start += step
    return windows


def run_walk_forward_backtest(
    bars: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    train_window: int,
    validation_window: int,
    test_window: int,
    step: int | None = None,
    config: BacktestConfig | None = None,
    model_id: str = "external_signal_model",
) -> dict[str, object]:
    """Evaluate precomputed signals in chronological walk-forward windows.

    The function intentionally does not train a model itself. It receives
    signals already produced by the caller and only evaluates each out-of-sample
    test slice, preserving the no-look-ahead contract for the backtest layer.
    """

    if bars.empty:
        return {"windows": [], "summary": {"window_count": 0}}
    work = bars.copy().sort_index()
    sig = signals.reindex(work.index).copy()
    windows = build_walk_forward_windows(
        work.index,
        train_window=train_window,
        validation_window=validation_window,
        test_window=test_window,
        step=step,
    )
    rows: list[dict[str, object]] = []
    for idx, window in enumerate(windows, start=1):
        test_bars = work.loc[window.test_start : window.test_end]
        test_signals = sig.loc[window.test_start : window.test_end]
        result = run_futures_backtest(test_bars, test_signals, config=config)
        rows.append(
            {
                "window_id": f"wf_{idx:04d}",
                "model_id": model_id,
                "periods": window.as_dict(),
                "oos_metrics": result["metrics"],
                "trade_list": result["trades"],
                "equity_curve": result["equity_curve"],
            }
        )
    summary = {
        "window_count": len(rows),
        "model_id": model_id,
        "train_window": train_window,
        "validation_window": validation_window,
        "test_window": test_window,
        "step": int(step or test_window),
    }
    return {"windows": rows, "summary": summary}
