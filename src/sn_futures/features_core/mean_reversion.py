from __future__ import annotations

import numpy as np
import pandas as pd

from .common import FactorSpec, finish, numeric, rolling_zscore
from .technical import _rsi


GROUP = "mean_reversion"


def build_mean_reversion_factors(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[FactorSpec], dict[str, str]]:
    out = pd.DataFrame(index=frame.index)
    missing: dict[str, str] = {}
    if "close" not in frame.columns:
        missing["close"] = "缺少均值回归因子必需字段：close"
    close = numeric(frame, "close")
    open_ = numeric(frame, "open")
    prev_close = close.shift(1)
    z20 = rolling_zscore(close, 20)
    z60 = rolling_zscore(close, 60)
    rsi = _rsi(close, 14)
    gap = open_ / prev_close.replace(0, np.nan) - 1.0

    out["zscore_close_20"] = z20
    out["zscore_close_60"] = z60
    out["rsi_reversal_14"] = (50.0 - rsi) / 50.0
    out["gap_reversion"] = -gap
    out["price_overextension_score"] = np.tanh(z20.fillna(0.0) / 2.0) + np.tanh(z60.fillna(0.0) / 2.5)

    metadata = [
        FactorSpec("zscore_close_20", GROUP, "均值回归", ("close",), "20期价格标准分", 20),
        FactorSpec("zscore_close_60", GROUP, "均值回归", ("close",), "60期价格标准分", 60),
        FactorSpec("rsi_reversal_14", GROUP, "反转", ("close",), "RSI偏离中轴后的反转压力", 14),
        FactorSpec("gap_reversion", GROUP, "跳空回补", ("open", "close"), "开盘跳空后的回补倾向", 2),
        FactorSpec("price_overextension_score", GROUP, "过度延伸", ("close",), "短中期价格过度延伸综合分", 60),
    ]
    return finish(out, metadata, missing)
