from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .costs import CostConfig, calculate_roll_cost


@dataclass(frozen=True)
class RollEvent:
    roll_date: str
    from_contract: str
    to_contract: str
    roll_cost: float


def detect_roll_events(
    frame: pd.DataFrame,
    *,
    contract_col: str = "main_contract",
    price_col: str = "close",
    contracts: int = 1,
    cost_config: CostConfig | None = None,
) -> list[RollEvent]:
    """Detect main-contract switches using only observed rows in sequence."""

    if contract_col not in frame.columns:
        return []
    cost_config = cost_config or CostConfig()
    events: list[RollEvent] = []
    previous = None
    for ts, row in frame.iterrows():
        current = str(row.get(contract_col, "") or "")
        if not current:
            continue
        if previous is not None and current != previous:
            price = float(row.get(price_col, 0.0) or 0.0)
            events.append(
                RollEvent(
                    roll_date=str(ts),
                    from_contract=previous,
                    to_contract=current,
                    roll_cost=calculate_roll_cost(price, contracts, cost_config),
                )
            )
        previous = current
    return events


def roll_cost_by_date(frame: pd.DataFrame, **kwargs) -> dict[pd.Timestamp, float]:
    events = detect_roll_events(frame, **kwargs)
    out: dict[pd.Timestamp, float] = {}
    for event in events:
        out[pd.Timestamp(event.roll_date)] = float(event.roll_cost)
    return out

