from __future__ import annotations

from dataclasses import dataclass, replace


@dataclass(frozen=True)
class CostConfig:
    commission_per_contract: float = 3.0
    commission_rate: float = 0.0
    slippage_ticks: float = 1.0
    tick_size: float = 10.0
    contract_multiplier: float = 1.0
    margin_rate: float = 0.14
    impact_cost_bps: float = 0.0
    roll_cost_bps: float = 1.0

    def scaled(self, multiplier: float) -> "CostConfig":
        return replace(
            self,
            commission_per_contract=self.commission_per_contract * multiplier,
            commission_rate=self.commission_rate * multiplier,
            slippage_ticks=self.slippage_ticks * multiplier,
            impact_cost_bps=self.impact_cost_bps * multiplier,
            roll_cost_bps=self.roll_cost_bps * multiplier,
        )


def notional(price: float, contracts: int, config: CostConfig) -> float:
    return abs(float(price) * int(contracts) * config.contract_multiplier)


def calculate_trade_cost(
    *,
    entry_price: float,
    exit_price: float,
    contracts: int,
    config: CostConfig,
    include_slippage: bool = True,
) -> dict[str, float]:
    entry_notional = notional(entry_price, contracts, config)
    exit_notional = notional(exit_price, contracts, config)
    commission = 2.0 * config.commission_per_contract * abs(int(contracts))
    commission += (entry_notional + exit_notional) * config.commission_rate
    slippage = (
        2.0 * config.slippage_ticks * config.tick_size * config.contract_multiplier * abs(int(contracts))
        if include_slippage
        else 0.0
    )
    impact = (entry_notional + exit_notional) * config.impact_cost_bps / 10_000.0
    total = commission + slippage + impact
    return {
        "commission_cost": float(commission),
        "slippage_cost": float(slippage),
        "impact_cost": float(impact),
        "total_cost": float(total),
    }


def calculate_roll_cost(price: float, contracts: int, config: CostConfig) -> float:
    return notional(price, contracts, config) * config.roll_cost_bps / 10_000.0

