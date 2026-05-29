from __future__ import annotations

import numpy as np
import pandas as pd

from .common import FactorSpec, finish, numeric, true_range


GROUP = "technical"
REQUIRED = ("open", "high", "low", "close", "volume")


def _rsi(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(period, min_periods=period).mean()
    loss = -delta.clip(upper=0).rolling(period, min_periods=period).mean()
    rs = gain / loss.replace(0, np.nan)
    return 100 - 100 / (1 + rs)


def _cci(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 20) -> pd.Series:
    typical = (high + low + close) / 3.0
    mean = typical.rolling(period, min_periods=period).mean()
    mad = (typical - mean).abs().rolling(period, min_periods=period).mean()
    return (typical - mean) / (0.015 * mad).replace(0, np.nan)


def build_technical_factors(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[FactorSpec], dict[str, str]]:
    out = pd.DataFrame(index=frame.index)
    missing: dict[str, str] = {}
    for column in REQUIRED:
        if column not in frame.columns:
            missing[column] = f"缺少技术因子必需字段：{column}"

    open_ = numeric(frame, "open")
    high = numeric(frame, "high")
    low = numeric(frame, "low")
    close = numeric(frame, "close")
    volume = numeric(frame, "volume").fillna(0.0)

    ema_5 = close.ewm(span=5, adjust=False).mean()
    ema_10 = close.ewm(span=10, adjust=False).mean()
    ema_20 = close.ewm(span=20, adjust=False).mean()
    ema_60 = close.ewm(span=60, adjust=False).mean()
    ma_20 = close.rolling(20, min_periods=20).mean()
    ma_60 = close.rolling(60, min_periods=60).mean()
    tr = true_range(frame)
    atr_14 = tr.rolling(14, min_periods=14).mean()
    mean_20 = close.rolling(20, min_periods=20).mean()
    std_20 = close.rolling(20, min_periods=20).std()
    obv = (np.sign(close.pct_change(fill_method=None).fillna(0.0)) * volume).cumsum()

    highest_20 = high.rolling(20, min_periods=20).max()
    lowest_20 = low.rolling(20, min_periods=20).min()
    highest_60 = high.rolling(60, min_periods=60).max()
    lowest_60 = low.rolling(60, min_periods=60).min()
    highest_14 = high.rolling(14, min_periods=14).max()
    lowest_14 = low.rolling(14, min_periods=14).min()

    out["ema_spread_5_20"] = ema_5 / ema_20 - 1.0
    out["ema_spread_10_60"] = ema_10 / ema_60 - 1.0
    out["ma_bias_20"] = close / ma_20 - 1.0
    out["ma_bias_60"] = close / ma_60 - 1.0
    out["roc_5"] = close.pct_change(5, fill_method=None)
    out["roc_10"] = close.pct_change(10, fill_method=None)
    out["roc_20"] = close.pct_change(20, fill_method=None)
    out["breakout_20"] = (close - highest_20.shift(1)) / atr_14.replace(0, np.nan)
    out["breakout_60"] = (close - highest_60.shift(1)) / atr_14.replace(0, np.nan)
    out["rsi_14"] = _rsi(close, 14)
    out["atr_14"] = atr_14
    out["bollinger_z_20"] = (close - mean_20) / std_20.replace(0, np.nan)
    out["cci_20"] = _cci(high, low, close, 20)
    out["wr_14"] = -100 * (highest_14 - close) / (highest_14 - lowest_14).replace(0, np.nan)
    out["obv_slope_10"] = obv - obv.shift(10)

    metadata = [
        FactorSpec(name, GROUP, "趋势/量价", REQUIRED, desc, lookback)
        for name, desc, lookback in [
            ("ema_spread_5_20", "5日与20日EMA差，衡量短趋势强度", 20),
            ("ema_spread_10_60", "10日与60日EMA差，衡量中期趋势强度", 60),
            ("ma_bias_20", "收盘价相对20日均线偏离", 20),
            ("ma_bias_60", "收盘价相对60日均线偏离", 60),
            ("roc_5", "5期动量收益", 5),
            ("roc_10", "10期动量收益", 10),
            ("roc_20", "20期动量收益", 20),
            ("breakout_20", "相对20期前高突破强度", 20),
            ("breakout_60", "相对60期前高突破强度", 60),
            ("rsi_14", "14期RSI强弱指标", 14),
            ("atr_14", "14期真实波幅", 14),
            ("bollinger_z_20", "20期布林标准分", 20),
            ("cci_20", "20期CCI商品通道指标", 20),
            ("wr_14", "14期威廉指标", 14),
            ("obv_slope_10", "10期OBV斜率，观察量价确认", 10),
        ]
    ]
    return finish(out, metadata, missing)
