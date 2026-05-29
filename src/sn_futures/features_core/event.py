from __future__ import annotations

import numpy as np
import pandas as pd

from .common import FactorSpec, finish, numeric


GROUP = "event"


def _rolling_count(series: pd.Series, window: int) -> pd.Series:
    return (series.fillna(0.0) > 0).astype(float).rolling(window, min_periods=1).sum()


def build_event_factors(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[FactorSpec], dict[str, str]]:
    out = pd.DataFrame(index=frame.index)
    missing: dict[str, str] = {}
    if "news_event_score" not in frame.columns and "event_score" not in frame.columns:
        missing["news_event_score"] = "缺少新闻/事件得分字段，事件因子按0降级"
    score = numeric(frame, "news_event_score")
    if score.isna().all():
        score = numeric(frame, "event_score", default=0.0).fillna(0.0)
    supply = numeric(frame, "supply_event_score", default=0.0).fillna(0.0)
    demand = numeric(frame, "demand_event_score", default=0.0).fillna(0.0)
    inventory = numeric(frame, "inventory_event_score", default=0.0).fillna(0.0)
    macro = numeric(frame, "macro_event_score", default=0.0).fillna(0.0)
    event_flag = ((score.abs() + supply.abs() + demand.abs() + inventory.abs() + macro.abs()) > 0).astype(float)

    age = pd.Series(np.arange(len(frame), dtype=float), index=frame.index)
    last_event_pos = age.where(event_flag > 0).ffill()
    recency = np.exp(-(age - last_event_pos).fillna(999.0) / 5.0)

    out["news_count_1d"] = _rolling_count(event_flag, 1)
    out["news_count_7d"] = _rolling_count(event_flag, 7)
    out["supply_shock_score"] = supply.rolling(3, min_periods=1).sum()
    out["demand_shock_score"] = demand.rolling(3, min_periods=1).sum()
    out["inventory_shock_score"] = inventory.rolling(3, min_periods=1).sum()
    out["macro_risk_score"] = macro.rolling(5, min_periods=1).sum()
    out["event_recency_decay_score"] = recency * score.fillna(0.0)
    out["event_vol_regime_shift"] = event_flag.rolling(5, min_periods=1).sum() * score.abs().rolling(5, min_periods=1).mean()

    metadata = [
        FactorSpec("news_count_1d", GROUP, "事件热度", ("news_event_score",), "近1期事件数量", 1),
        FactorSpec("news_count_7d", GROUP, "事件热度", ("news_event_score",), "近7期事件数量", 7),
        FactorSpec("supply_shock_score", GROUP, "供应冲击", ("supply_event_score",), "供应扰动事件得分", 3),
        FactorSpec("demand_shock_score", GROUP, "需求冲击", ("demand_event_score",), "需求变化事件得分", 3),
        FactorSpec("inventory_shock_score", GROUP, "库存冲击", ("inventory_event_score",), "库存/仓单事件得分", 3),
        FactorSpec("macro_risk_score", GROUP, "宏观风险", ("macro_event_score",), "宏观政策/利率/美元事件得分", 5),
        FactorSpec("event_recency_decay_score", GROUP, "事件衰减", ("news_event_score",), "按时间衰减的事件影响", 5),
        FactorSpec("event_vol_regime_shift", GROUP, "事件波动", ("news_event_score",), "事件驱动波动状态切换", 5),
    ]
    return finish(out, metadata, missing)
