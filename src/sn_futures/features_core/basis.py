from __future__ import annotations

import numpy as np
import pandas as pd

from .common import FactorSpec, finish, numeric, percentile_rank, rolling_zscore


GROUP = "basis"


def build_basis_factors(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[FactorSpec], dict[str, str]]:
    out = pd.DataFrame(index=frame.index)
    missing: dict[str, str] = {}
    if "spot_price" not in frame.columns:
        missing["spot_price"] = "缺少现货价格 spot_price，基差类因子降级为数据暂缺"
    if "close" not in frame.columns:
        missing["close"] = "缺少期货收盘价 close，基差类因子降级为数据暂缺"
    close = numeric(frame, "close")
    spot = numeric(frame, "spot_price")
    spot_premium = numeric(frame, "spot_premium")
    basis = spot - close
    out["spot_futures_basis"] = basis
    out["basis_zscore_60"] = rolling_zscore(basis, 60)
    out["basis_mom_5"] = basis.diff(5)
    out["basis_mom_20"] = basis.diff(20)
    out["basis_percentile_252"] = percentile_rank(basis, 252)
    out["spot_premium_mom"] = spot_premium.diff(5)
    out["delivery_basis_momentum"] = basis.diff(5) * numeric(frame, "delivery_month_flag", default=0.0).fillna(0.0)
    out["cash_tightness_score"] = rolling_zscore(basis, 60).fillna(0.0) + rolling_zscore(spot_premium, 60).fillna(0.0)

    metadata = [
        FactorSpec("spot_futures_basis", GROUP, "现货紧张", ("spot_price", "close"), "现货-期货基差", 1),
        FactorSpec("basis_zscore_60", GROUP, "现货紧张", ("spot_price", "close"), "60期基差标准分", 60),
        FactorSpec("basis_mom_5", GROUP, "基差动量", ("spot_price", "close"), "5期基差变化", 5),
        FactorSpec("basis_mom_20", GROUP, "基差动量", ("spot_price", "close"), "20期基差变化", 20),
        FactorSpec("basis_percentile_252", GROUP, "基差分位", ("spot_price", "close"), "252期基差历史分位", 252),
        FactorSpec("spot_premium_mom", GROUP, "升贴水动量", ("spot_premium",), "现货升贴水5期变化", 5),
        FactorSpec("delivery_basis_momentum", GROUP, "交割月基差", ("delivery_month_flag", "spot_price", "close"), "交割月基差动量", 5),
        FactorSpec("cash_tightness_score", GROUP, "现货紧张", ("spot_price", "close", "spot_premium"), "基差与升贴水综合紧张度", 60),
    ]
    return finish(out, metadata, missing)
