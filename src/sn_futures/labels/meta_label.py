from __future__ import annotations

import pandas as pd


LONG_SIGNAL = "long_candidate"
SHORT_SIGNAL = "short_candidate"
NO_TRADE_SIGNAL = "no_trade"


def add_meta_labels(
    frame: pd.DataFrame,
    *,
    primary_signal_col: str = "primary_signal",
    tb_label_col: str = "tb_label",
    side_adjusted_tb: bool = True,
) -> pd.DataFrame:
    """Build meta-labels for candidate trade filtering.

    Rows with ``primary_signal == no_trade`` are excluded from meta-model
    training by assigning missing targets.
    """

    if primary_signal_col not in frame.columns:
        raise KeyError(f"Missing primary signal column: {primary_signal_col}")
    if tb_label_col not in frame.columns:
        raise KeyError(f"Missing triple-barrier label column: {tb_label_col}")

    out = frame.copy()
    signal = out[primary_signal_col].astype(str)
    tb = pd.to_numeric(out[tb_label_col], errors="coerce")

    long_ok = (signal == LONG_SIGNAL) & (tb == 1)
    if side_adjusted_tb:
        short_ok = (signal == SHORT_SIGNAL) & (tb == 1)
    else:
        short_ok = (signal == SHORT_SIGNAL) & (tb == -1)
    candidate = signal.isin([LONG_SIGNAL, SHORT_SIGNAL])
    success = candidate & (long_ok | short_ok)

    out["meta_target"] = pd.Series(pd.NA, index=out.index, dtype="Int64")
    out.loc[candidate, "meta_target"] = 0
    out.loc[success, "meta_target"] = 1
    out["meta_label"] = pd.Series(pd.NA, index=out.index, dtype="object")
    out.loc[candidate, "meta_label"] = "skip"
    out.loc[success, "meta_label"] = "trade"
    return out

