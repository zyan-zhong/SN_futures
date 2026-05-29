from __future__ import annotations

import numpy as np
import pandas as pd

from .common import FactorSpec, finish, numeric, percentile_rank, rolling_zscore


GROUP = "inventory"


def build_inventory_factors(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[FactorSpec], dict[str, str]]:
    out = pd.DataFrame(index=frame.index)
    missing: dict[str, str] = {}
    for column in ("shfe_inventory", "lme_inventory"):
        if column not in frame.columns:
            missing[column] = f"缺少库存字段：{column}，相关因子降级为数据暂缺"
    shfe = numeric(frame, "shfe_inventory")
    lme = numeric(frame, "lme_inventory")
    bonded = numeric(frame, "bonded_inventory", default=0.0).fillna(0.0)
    global_visible = shfe.fillna(0.0) + lme.fillna(0.0) + bonded

    out["shfe_inventory_delta_1w"] = shfe.diff(5)
    out["shfe_inventory_delta_4w"] = shfe.diff(20)
    out["lme_inventory_delta_1w"] = lme.diff(5)
    out["global_visible_inventory"] = global_visible
    out["inventory_percentile_3y"] = percentile_rank(global_visible, 756)
    out["inventory_pressure_score"] = rolling_zscore(global_visible, 252).fillna(0.0) + rolling_zscore(shfe.diff(20), 120).fillna(0.0)

    metadata = [
        FactorSpec("shfe_inventory_delta_1w", GROUP, "库存变化", ("shfe_inventory",), "上期所库存1周变化", 5),
        FactorSpec("shfe_inventory_delta_4w", GROUP, "库存变化", ("shfe_inventory",), "上期所库存4周变化", 20),
        FactorSpec("lme_inventory_delta_1w", GROUP, "外盘库存", ("lme_inventory",), "LME库存1周变化", 5),
        FactorSpec("global_visible_inventory", GROUP, "显性库存", ("shfe_inventory", "lme_inventory"), "SHFE+LME+保税区显性库存", 1),
        FactorSpec("inventory_percentile_3y", GROUP, "库存分位", ("shfe_inventory", "lme_inventory"), "三年显性库存分位", 756),
        FactorSpec("inventory_pressure_score", GROUP, "库存压力", ("shfe_inventory", "lme_inventory"), "库存水平与变化综合压力", 252),
    ]
    return finish(out, metadata, missing)
