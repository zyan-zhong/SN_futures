from __future__ import annotations

import numpy as np
import pandas as pd

from .common import FactorSpec, finish, numeric, true_range


GROUP = "regime"


def build_regime_factors(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[FactorSpec], dict[str, str]]:
    out = pd.DataFrame(index=frame.index)
    missing: dict[str, str] = {}
    if "close" not in frame.columns:
        missing["close"] = "缺少 close，市场状态降级为 RANGE_LOW_VOL"
    close = numeric(frame, "close")
    volume = numeric(frame, "volume")
    open_interest = numeric(frame, "open_interest")
    event_score = numeric(frame, "news_event_score")
    if event_score.isna().all():
        event_score = numeric(frame, "event_score", default=0.0).fillna(0.0)

    ret = close.pct_change(fill_method=None)
    trend_20 = close / close.rolling(20, min_periods=10).mean() - 1.0
    vol_20 = ret.rolling(20, min_periods=10).std()
    high_vol_threshold = vol_20.rolling(120, min_periods=30).median()
    atr_pct = true_range(frame).rolling(14, min_periods=10).mean() / close.replace(0, np.nan)
    volume_z = (volume - volume.rolling(20, min_periods=10).mean()) / volume.rolling(20, min_periods=10).std().replace(0, np.nan)
    oi_chg = open_interest.pct_change(5, fill_method=None)
    event_flag = event_score.abs() >= max(0.35, float(event_score.abs().quantile(0.90)) if len(event_score.dropna()) else 0.35)

    labels: list[str] = []
    for idx in frame.index:
        tr = float(trend_20.get(idx, 0.0) or 0.0)
        vol = float(vol_20.get(idx, 0.0) or 0.0)
        hv = float(high_vol_threshold.get(idx, np.nan))
        is_high_vol = bool(np.isfinite(hv) and vol > hv)
        if bool(event_flag.get(idx, False)):
            labels.append("EVENT_SHOCK")
        elif float(volume_z.get(idx, 0.0) or 0.0) < -1.5 and abs(float(oi_chg.get(idx, 0.0) or 0.0)) > 0.05:
            labels.append("LIQUIDITY_THIN")
        elif abs(tr) < 0.012:
            labels.append("RANGE_HIGH_VOL" if is_high_vol else "RANGE_LOW_VOL")
        elif tr > 0:
            labels.append("TREND_UP_HIGH_VOL" if is_high_vol else "TREND_UP_LOW_VOL")
        else:
            labels.append("TREND_DOWN_HIGH_VOL" if is_high_vol else "TREND_DOWN_LOW_VOL")

    out["regime_label"] = pd.Series(labels, index=frame.index).fillna("RANGE_LOW_VOL")
    out["regime_volatility_score"] = atr_pct
    out["regime_trend_score"] = trend_20

    metadata = [
        FactorSpec("regime_label", GROUP, "市场状态", ("close", "volume", "open_interest"), "趋势/震荡/事件/流动性状态标签", 20),
        FactorSpec("regime_volatility_score", GROUP, "波动状态", ("open", "high", "low", "close"), "ATR占价格比例", 14),
        FactorSpec("regime_trend_score", GROUP, "趋势状态", ("close",), "20期趋势偏离", 20),
    ]
    return finish(out, metadata, missing)
