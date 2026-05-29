from __future__ import annotations

import numpy as np
import pandas as pd

from .common import FactorSpec, finish, numeric


GROUP = "term_structure"
REQUIRED = ("near_contract_close", "far_contract_close")


def build_term_structure_factors(frame: pd.DataFrame) -> tuple[pd.DataFrame, list[FactorSpec], dict[str, str]]:
    out = pd.DataFrame(index=frame.index)
    missing: dict[str, str] = {}
    for column in REQUIRED:
        if column not in frame.columns:
            missing[column] = f"缺少多合约期限结构字段：{column}，相关因子降级为数据暂缺"
    near = numeric(frame, "near_contract_close")
    far = numeric(frame, "far_contract_close")
    near_oi = numeric(frame, "near_open_interest")
    far_oi = numeric(frame, "far_open_interest")
    main_contract = frame["main_contract"] if "main_contract" in frame.columns else pd.Series("", index=frame.index)

    spread = near - far
    slope = spread / near.replace(0, np.nan)
    out["near_far_spread"] = spread
    out["term_structure_slope"] = slope
    out["calendar_spread_momentum"] = spread.diff(5)
    out["roll_yield_proxy"] = (far / near.replace(0, np.nan) - 1.0)
    out["open_interest_roll_ratio"] = near_oi / far_oi.replace(0, np.nan)
    out["main_contract_switch_flag"] = (main_contract.astype(str) != main_contract.astype(str).shift(1)).astype(float)
    out.loc[out.index[:1], "main_contract_switch_flag"] = 0.0

    metadata = [
        FactorSpec("near_far_spread", GROUP, "期限价差", REQUIRED, "近远月合约价差", 1),
        FactorSpec("term_structure_slope", GROUP, "期限结构", REQUIRED, "近远月价差相对近月价格的斜率", 1),
        FactorSpec("calendar_spread_momentum", GROUP, "期限动量", REQUIRED, "近远月价差5期变化", 5),
        FactorSpec("roll_yield_proxy", GROUP, "移仓收益", REQUIRED, "远近月价差构造的展期收益代理", 1),
        FactorSpec("open_interest_roll_ratio", GROUP, "换月流动性", ("near_open_interest", "far_open_interest"), "近远月持仓比", 1),
        FactorSpec("main_contract_switch_flag", GROUP, "换月", ("main_contract",), "主力合约切换标记", 1),
    ]
    return finish(out, metadata, missing)
