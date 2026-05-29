from __future__ import annotations

import numpy as np
import pandas as pd

from .common import FactorSpec, finish, numeric, rolling_zscore


GROUP = "cross_market"


def build_cross_market_factors(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[FactorSpec], dict[str, str]]:
    out = pd.DataFrame(index=frame.index)
    missing: dict[str, str] = {}
    for column in ("lme_tin_close", "usd_cny"):
        if column not in frame.columns:
            missing[column] = f"缺少跨市场字段：{column}，相关因子降级为数据暂缺"
    lme = numeric(frame, "lme_tin_close")
    close = numeric(frame, "close")
    usd_cny = numeric(frame, "usd_cny")
    dxy = numeric(frame, "dxy")
    us10y = numeric(frame, "us10y")

    out["lme_tin_return_1d"] = lme.pct_change(1, fill_method=None)
    out["lme_tin_return_3d"] = lme.pct_change(3, fill_method=None)
    out["lme_tin_overnight_return"] = numeric(frame, "lme_overnight_return")
    out["lme_shfe_spread"] = lme * usd_cny - close
    out["usd_cny_return"] = usd_cny.pct_change(1, fill_method=None)
    out["dxy_return"] = dxy.pct_change(1, fill_method=None)
    out["us10y_change"] = us10y.diff(1)
    risk_proxy = -rolling_zscore(dxy.pct_change(5, fill_method=None), 60).fillna(0.0) - rolling_zscore(us10y.diff(5), 60).fillna(0.0)
    out["global_risk_sentiment_proxy"] = risk_proxy

    metadata = [
        FactorSpec("lme_tin_return_1d", GROUP, "外盘联动", ("lme_tin_close",), "LME锡1日收益", 1),
        FactorSpec("lme_tin_return_3d", GROUP, "外盘联动", ("lme_tin_close",), "LME锡3日收益", 3),
        FactorSpec("lme_tin_overnight_return", GROUP, "隔夜外盘", ("lme_overnight_return",), "LME锡隔夜收益", 1),
        FactorSpec("lme_shfe_spread", GROUP, "内外盘价差", ("lme_tin_close", "usd_cny", "close"), "LME折人民币与沪锡价差", 1),
        FactorSpec("usd_cny_return", GROUP, "汇率", ("usd_cny",), "美元兑人民币变化", 1),
        FactorSpec("dxy_return", GROUP, "美元指数", ("dxy",), "美元指数变化", 1),
        FactorSpec("us10y_change", GROUP, "利率", ("us10y",), "美国10年期收益率变化", 1),
        FactorSpec("global_risk_sentiment_proxy", GROUP, "全球风险偏好", ("dxy", "us10y"), "美元与利率构造的全球风险偏好代理", 60),
    ]
    return finish(out, metadata, missing)
