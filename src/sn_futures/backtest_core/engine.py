from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

import numpy as np
import pandas as pd

from .contract_roll import roll_cost_by_date
from .costs import CostConfig, calculate_trade_cost
from .metrics import compute_backtest_metrics, coverage_by_signal_strength
from .slippage import apply_slippage


ExecutionMode = Literal["next_open", "next_close"]


@dataclass(frozen=True)
class BacktestConfig:
    initial_equity: float = 1_000_000.0
    execution_mode: ExecutionMode = "next_open"
    max_position: int = 1
    max_daily_loss: float = 0.03
    max_drawdown_stop: float = 0.20
    volatility_targeting: bool = False
    target_volatility: float = 0.15
    atr_stop_multiple: float = 1.5
    trailing_stop_multiple: float = 2.0
    no_trade_when_data_quality_low: float = 0.45
    conservative_intrabar: bool = True
    cost: CostConfig = field(default_factory=CostConfig)


def _entry_price(row: pd.Series, mode: ExecutionMode) -> float:
    if mode == "next_close":
        return float(row.get("close", np.nan))
    return float(row.get("open", row.get("close", np.nan)))


def _exit_from_bar(
    row: pd.Series,
    *,
    signal: int,
    stop_price: float,
    take_profit: float,
    trailing_stop: float | None = None,
    conservative: bool,
) -> tuple[float, str]:
    close = float(row.get("close", np.nan))
    high = row.get("high", np.nan)
    low = row.get("low", np.nan)
    if not np.isfinite(high) or not np.isfinite(low):
        return close, "close_only"
    high = float(high)
    low = float(low)
    if signal > 0:
        if trailing_stop is not None and np.isfinite(trailing_stop):
            stop_price = max(stop_price, float(trailing_stop))
        hit_stop = low <= stop_price
        hit_take = high >= take_profit
        if hit_stop and hit_take:
            return (stop_price if conservative else take_profit), "both_conservative_stop" if conservative else "both_take"
        if hit_stop:
            return stop_price, "stop_loss"
        if hit_take:
            return take_profit, "take_profit"
    else:
        if trailing_stop is not None and np.isfinite(trailing_stop):
            stop_price = min(stop_price, float(trailing_stop))
        hit_stop = high >= stop_price
        hit_take = low <= take_profit
        if hit_stop and hit_take:
            return (stop_price if conservative else take_profit), "both_conservative_stop" if conservative else "both_take"
        if hit_stop:
            return stop_price, "stop_loss"
        if hit_take:
            return take_profit, "take_profit"
    return close, "bar_close"


def _position_size(row: pd.Series, config: BacktestConfig, equity: float, entry: float, stop: float) -> int:
    max_position = int(config.max_position)
    if max_position <= 0 or entry <= 0:
        return 0
    if config.volatility_targeting:
        vol = float(row.get("expected_volatility", row.get("realized_vol_5d", 0.0)) or 0.0)
        if vol > 0:
            scaled = max(1, int(max_position * min(1.0, config.target_volatility / max(vol, 1e-8))))
            max_position = min(max_position, scaled)
    margin_per_contract = entry * config.cost.contract_multiplier * config.cost.margin_rate
    margin_cap = int(equity // max(margin_per_contract, 1.0))
    risk_per_contract = abs(entry - stop) * config.cost.contract_multiplier
    if risk_per_contract > 0:
        loss_cap = int((equity * config.max_daily_loss) // risk_per_contract)
        max_position = min(max_position, max(1, loss_cap))
    return max(0, min(max_position, margin_cap))


def _parse_signal(value: object) -> int:
    if value is None:
        return 0
    if isinstance(value, str):
        text = value.strip().lower()
        if not text or text in {"0", "neutral", "no_trade", "观望", "仅观望"}:
            return 0
        if text in {"1", "long", "buy", "up", "long_candidate", "多头研究观察"}:
            return 1
        if text in {"-1", "short", "sell", "down", "short_candidate", "空头研究观察"}:
            return -1
        return 0
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0
    if not np.isfinite(number) or abs(number) < 1e-12:
        return 0
    return 1 if number > 0 else -1


def run_futures_backtest(
    bars: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    config: BacktestConfig | None = None,
) -> dict[str, object]:
    config = config or BacktestConfig()
    if bars.empty:
        return {"trades": pd.DataFrame(), "equity_curve": pd.Series(dtype=float), "metrics": {}, "diagnostics": {}}
    work = bars.copy().sort_index()
    sig = signals.reindex(work.index).copy()
    if "signal" not in sig.columns:
        sig["signal"] = 0
    equity = float(config.initial_equity)
    peak_equity = equity
    halted = False
    equity_points: list[tuple[pd.Timestamp, float]] = []
    trades: list[dict[str, object]] = []
    roll_costs = roll_cost_by_date(work, contracts=max(1, config.max_position), cost_config=config.cost)

    for pos in range(len(work)):
        ts = pd.Timestamp(work.index[pos])
        if ts in roll_costs:
            equity -= roll_costs[ts]
        equity_points.append((ts, equity))
        if halted or pos + 1 >= len(work):
            continue
        signal = _parse_signal(sig.iloc[pos].get("signal", 0))
        if signal == 0:
            continue
        edge = float(sig.iloc[pos].get("trade_edge", sig.iloc[pos].get("edge", 1.0)) or 0.0)
        if edge <= 0:
            continue
        quality = float(sig.iloc[pos].get("data_quality_score", work.iloc[pos].get("data_quality_score", 1.0)) or 0.0)
        if quality < config.no_trade_when_data_quality_low:
            continue

        next_row = work.iloc[pos + 1]
        trade_ts = pd.Timestamp(work.index[pos + 1])
        raw_entry = _entry_price(next_row, config.execution_mode)
        if not np.isfinite(raw_entry):
            continue
        entry = apply_slippage(
            raw_entry,
            signal=signal,
            is_entry=True,
            tick_size=config.cost.tick_size,
            slippage_ticks=config.cost.slippage_ticks,
        )
        atr = float(sig.iloc[pos].get("atr_14", work.iloc[pos].get("atr_14", entry * 0.012)) or entry * 0.012)
        if signal > 0:
            stop = float(sig.iloc[pos].get("stop_loss", entry - config.atr_stop_multiple * atr))
            take = float(sig.iloc[pos].get("take_profit", entry + config.atr_stop_multiple * atr * 2.0))
        else:
            stop = float(sig.iloc[pos].get("stop_loss", entry + config.atr_stop_multiple * atr))
            take = float(sig.iloc[pos].get("take_profit", entry - config.atr_stop_multiple * atr * 2.0))
        contracts = _position_size(sig.iloc[pos], config, equity, entry, stop)
        if contracts <= 0:
            continue

        raw_exit, exit_reason = _exit_from_bar(
            next_row,
            signal=signal,
            stop_price=stop,
            take_profit=take,
            trailing_stop=sig.iloc[pos].get("trailing_stop", np.nan),
            conservative=config.conservative_intrabar,
        )
        exit_price = apply_slippage(
            raw_exit,
            signal=signal,
            is_entry=False,
            tick_size=config.cost.tick_size,
            slippage_ticks=config.cost.slippage_ticks,
        )
        gross_pnl = signal * (exit_price - entry) * config.cost.contract_multiplier * contracts
        cost = calculate_trade_cost(entry_price=entry, exit_price=exit_price, contracts=contracts, config=config.cost, include_slippage=False)
        net_pnl = gross_pnl - cost["total_cost"]
        equity += net_pnl
        peak_equity = max(peak_equity, equity)
        drawdown = equity / max(peak_equity, 1e-12) - 1.0
        if drawdown <= -abs(config.max_drawdown_stop):
            halted = True
        trades.append(
            {
                "signal_time": ts,
                "entry_time": trade_ts,
                "exit_time": trade_ts,
                "signal": signal,
                "entry_price": entry,
                "exit_price": exit_price,
                "contracts": contracts,
                "gross_pnl": gross_pnl,
                "net_pnl": net_pnl,
                "pnl": net_pnl,
                **cost,
                "exit_reason": exit_reason,
                "holding_period": 1,
                "turnover": (abs(entry) + abs(exit_price)) * contracts * config.cost.contract_multiplier,
                "confidence": sig.iloc[pos].get("confidence_score", sig.iloc[pos].get("confidence", np.nan)),
                "signal_strength": sig.iloc[pos].get("signal_strength", ""),
                "regime": sig.iloc[pos].get("regime", sig.iloc[pos].get("regime_label", "")),
                "horizon": sig.iloc[pos].get("horizon", ""),
            }
        )
        equity_points[-1] = (ts, equity)

    equity_curve = pd.Series([value for _, value in equity_points], index=[ts for ts, _ in equity_points], name="equity")
    trade_frame = pd.DataFrame(trades)
    metrics = compute_backtest_metrics(equity_curve, trade_frame)
    diagnostics = {"coverage_by_signal_strength": coverage_by_signal_strength(trade_frame)}
    return {"trades": trade_frame, "equity_curve": equity_curve, "metrics": metrics, "diagnostics": diagnostics}
