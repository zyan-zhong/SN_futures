from __future__ import annotations

import numpy as np
import pandas as pd


def _safe_div(num: float, den: float, default: float = 0.0) -> float:
    return float(num / den) if abs(den) > 1e-12 else float(default)


def compute_drawdown(equity: pd.Series) -> pd.Series:
    clean = pd.to_numeric(equity, errors="coerce").ffill().fillna(0.0)
    running = clean.cummax().replace(0, np.nan)
    return clean / running - 1.0


def compute_backtest_metrics(equity_curve: pd.Series, trades: pd.DataFrame, *, periods_per_year: int = 252) -> dict[str, float]:
    equity = pd.to_numeric(equity_curve, errors="coerce").dropna()
    if equity.empty:
        return {}
    returns = equity.pct_change().fillna(0.0)
    drawdown = compute_drawdown(equity)
    cumulative_return = _safe_div(float(equity.iloc[-1] - equity.iloc[0]), float(equity.iloc[0]))
    annual_return = (1.0 + cumulative_return) ** (periods_per_year / max(len(equity), 1)) - 1.0
    annual_vol = float(returns.std(ddof=1) * np.sqrt(periods_per_year)) if len(returns) > 1 else 0.0
    downside = returns.where(returns < 0, 0.0)
    downside_vol = float(downside.std(ddof=1) * np.sqrt(periods_per_year)) if len(returns) > 1 else 0.0
    sharpe = _safe_div(float(returns.mean() * periods_per_year), annual_vol)
    sortino = _safe_div(float(returns.mean() * periods_per_year), downside_vol)
    max_drawdown = float(drawdown.min()) if not drawdown.empty else 0.0
    calmar = _safe_div(float(annual_return), abs(max_drawdown))

    if trades.empty:
        wins = pd.Series(dtype=float)
        losses = pd.Series(dtype=float)
        pnl = pd.Series(dtype=float)
    else:
        pnl = pd.to_numeric(trades.get("net_pnl", trades.get("pnl", pd.Series(dtype=float))), errors="coerce").fillna(0.0)
        wins = pnl[pnl > 0]
        losses = pnl[pnl < 0]
    trade_count = int(len(pnl))
    win_rate = float((pnl > 0).mean()) if trade_count else 0.0
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(losses.mean()) if not losses.empty else 0.0
    payoff_ratio = _safe_div(abs(avg_win), abs(avg_loss))
    expectancy = float(pnl.mean()) if trade_count else 0.0
    profit_factor = _safe_div(float(wins.sum()), abs(float(losses.sum())))
    costs = pd.to_numeric(trades.get("total_cost", pd.Series(dtype=float)), errors="coerce").fillna(0.0) if not trades.empty else pd.Series(dtype=float)
    gross = pd.to_numeric(trades.get("gross_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0) if not trades.empty else pd.Series(dtype=float)
    holding = pd.to_numeric(trades.get("holding_period", pd.Series(dtype=float)), errors="coerce").fillna(0.0) if not trades.empty else pd.Series(dtype=float)
    turnover = pd.to_numeric(trades.get("turnover", pd.Series(dtype=float)), errors="coerce").fillna(0.0) if not trades.empty else pd.Series(dtype=float)
    high_conf = trades[pd.to_numeric(trades.get("confidence", 0.0), errors="coerce").fillna(0.0) >= 80] if not trades.empty and "confidence" in trades.columns else pd.DataFrame()
    high_conf_pnl = pd.to_numeric(high_conf.get("net_pnl", pd.Series(dtype=float)), errors="coerce").fillna(0.0) if not high_conf.empty else pd.Series(dtype=float)

    return {
        "cumulative_return": float(cumulative_return),
        "annual_return": float(annual_return),
        "annual_volatility": annual_vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": max_drawdown,
        "win_rate": win_rate,
        "payoff_ratio": payoff_ratio,
        "expectancy": expectancy,
        "profit_factor": profit_factor,
        "trade_count": float(trade_count),
        "avg_holding_period": float(holding.mean()) if not holding.empty else 0.0,
        "turnover": float(turnover.sum()),
        "net_profit_after_cost": float(pnl.sum()) if trade_count else 0.0,
        "break_even_cost": float(gross.sum()) if not gross.empty else 0.0,
        "total_cost": float(costs.sum()) if not costs.empty else 0.0,
        "high_conf_hit_rate": float((high_conf_pnl > 0).mean()) if not high_conf_pnl.empty else 0.0,
    }


def coverage_by_signal_strength(trades: pd.DataFrame) -> dict[str, dict[str, float]]:
    if trades.empty or "signal_strength" not in trades.columns:
        return {}
    out: dict[str, dict[str, float]] = {}
    for strength, group in trades.groupby("signal_strength"):
        pnl = pd.to_numeric(group.get("net_pnl", group.get("pnl", 0.0)), errors="coerce").fillna(0.0)
        out[str(strength)] = {
            "trade_count": float(len(group)),
            "win_rate": float((pnl > 0).mean()) if len(group) else 0.0,
            "net_profit_after_cost": float(pnl.sum()),
        }
    return out

