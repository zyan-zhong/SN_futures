from __future__ import annotations

from dataclasses import replace

import numpy as np
import pandas as pd

from .engine import BacktestConfig, run_futures_backtest
from .metrics import coverage_by_signal_strength


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _group_performance(trades: pd.DataFrame, column: str) -> list[dict[str, object]]:
    if trades.empty or column not in trades.columns:
        return []
    rows: list[dict[str, object]] = []
    for key, group in trades.groupby(column, dropna=False):
        pnl = pd.to_numeric(group.get("net_pnl", group.get("pnl", 0.0)), errors="coerce").fillna(0.0)
        rows.append(
            {
                str(column): "" if pd.isna(key) else str(key),
                "trade_count": int(len(group)),
                "win_rate": float((pnl > 0).mean()) if len(group) else 0.0,
                "net_profit_after_cost": float(pnl.sum()),
                "avg_trade_pnl": float(pnl.mean()) if len(group) else 0.0,
            }
        )
    return sorted(rows, key=lambda row: row["trade_count"], reverse=True)


def drawdown_periods(equity_curve: pd.Series, *, top_n: int = 5) -> list[dict[str, object]]:
    if equity_curve.empty:
        return []
    equity = pd.to_numeric(equity_curve, errors="coerce").dropna()
    running = equity.cummax()
    dd = equity / running.replace(0, np.nan) - 1.0
    periods: list[dict[str, object]] = []
    in_dd = False
    start = trough = None
    trough_value = 0.0
    for ts, value in dd.items():
        if value < 0 and not in_dd:
            in_dd = True
            start = pd.Timestamp(ts)
            trough = pd.Timestamp(ts)
            trough_value = float(value)
        elif value < 0 and in_dd:
            if float(value) < trough_value:
                trough = pd.Timestamp(ts)
                trough_value = float(value)
        elif value >= 0 and in_dd:
            periods.append(
                {
                    "start": start.isoformat() if start is not None else "",
                    "trough": trough.isoformat() if trough is not None else "",
                    "end": pd.Timestamp(ts).isoformat(),
                    "max_drawdown": trough_value,
                }
            )
            in_dd = False
    if in_dd:
        periods.append(
            {
                "start": start.isoformat() if start is not None else "",
                "trough": trough.isoformat() if trough is not None else "",
                "end": pd.Timestamp(equity.index[-1]).isoformat(),
                "max_drawdown": trough_value,
            }
        )
    return sorted(periods, key=lambda row: row["max_drawdown"])[:top_n]


def recent_degradation(trades: pd.DataFrame, *, recent_n: int = 20) -> dict[str, float | str]:
    if trades.empty or len(trades) < max(4, recent_n // 2):
        return {"status": "样本不足", "recent_win_rate": 0.0, "prior_win_rate": 0.0}
    pnl = pd.to_numeric(trades.get("net_pnl", trades.get("pnl", 0.0)), errors="coerce").fillna(0.0)
    recent = pnl.tail(recent_n)
    prior = pnl.iloc[: -len(recent)] if len(pnl) > len(recent) else pnl.iloc[:0]
    recent_win = float((recent > 0).mean()) if len(recent) else 0.0
    prior_win = float((prior > 0).mean()) if len(prior) else recent_win
    status = "近期退化" if recent_win + 0.12 < prior_win else "稳定"
    return {"status": status, "recent_win_rate": recent_win, "prior_win_rate": prior_win}


def build_backtest_diagnostics(
    *,
    trades: pd.DataFrame,
    equity_curve: pd.Series,
    metrics: dict[str, float],
    benchmark_metrics: dict[str, float] | None = None,
) -> dict[str, object]:
    benchmark_metrics = benchmark_metrics or {}
    baseline_comparison = {
        "strategy_net_profit_after_cost": _safe_float(metrics.get("net_profit_after_cost")),
        "benchmark_net_profit_after_cost": _safe_float(benchmark_metrics.get("net_profit_after_cost")),
        "strategy_sharpe": _safe_float(metrics.get("sharpe")),
        "benchmark_sharpe": _safe_float(benchmark_metrics.get("sharpe")),
        "strategy_max_drawdown": _safe_float(metrics.get("max_drawdown")),
        "benchmark_max_drawdown": _safe_float(benchmark_metrics.get("max_drawdown")),
    }
    if trades.empty:
        worst_trades: list[dict[str, object]] = []
    else:
        worst = trades.copy()
        worst["net_pnl"] = pd.to_numeric(worst.get("net_pnl", worst.get("pnl", 0.0)), errors="coerce").fillna(0.0)
        worst_trades = worst.nsmallest(10, "net_pnl").to_dict(orient="records")
    signal_strength = coverage_by_signal_strength(trades)
    return {
        "baseline_comparison": baseline_comparison,
        "by_regime_performance": _group_performance(trades, "regime"),
        "by_horizon_performance": _group_performance(trades, "horizon"),
        "by_signal_strength_performance": [
            {"signal_strength": key, **value} for key, value in signal_strength.items()
        ],
        "drawdown_periods": drawdown_periods(equity_curve),
        "worst_trades": worst_trades,
        "recent_degradation": recent_degradation(trades),
    }


def run_cost_sensitivity(
    bars: pd.DataFrame,
    signals: pd.DataFrame,
    *,
    config: BacktestConfig | None = None,
    multipliers: tuple[float, ...] = (0.5, 1.0, 2.0, 3.0),
) -> pd.DataFrame:
    base_config = config or BacktestConfig()
    rows: list[dict[str, object]] = []
    for multiplier in multipliers:
        scenario_config = replace(base_config, cost=base_config.cost.scaled(multiplier))
        result = run_futures_backtest(bars, signals, config=scenario_config)
        metrics = result.get("metrics", {})
        net_profit = _safe_float(metrics.get("net_profit_after_cost")) if isinstance(metrics, dict) else 0.0
        rows.append(
            {
                "cost_multiplier": float(multiplier),
                "net_profit_after_cost": net_profit,
                "cumulative_return": _safe_float(metrics.get("cumulative_return")) if isinstance(metrics, dict) else 0.0,
                "sharpe": _safe_float(metrics.get("sharpe")) if isinstance(metrics, dict) else 0.0,
                "trade_count": _safe_float(metrics.get("trade_count")) if isinstance(metrics, dict) else 0.0,
                "positive_after_cost": bool(net_profit > 0),
            }
        )
    return pd.DataFrame(rows)
