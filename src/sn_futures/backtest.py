from __future__ import annotations

import numpy as np
import pandas as pd

from .compliance import signal_label
from .config import RiskConfig


def build_research_signals(predictions: pd.DataFrame, risk: RiskConfig | None = None) -> pd.DataFrame:
    risk = risk or RiskConfig()
    work = predictions.copy()
    prob_series = work["prob_up_multimodal"] if "prob_up_multimodal" in work.columns else work["prob_up"]
    confidence_series = work["confidence_multimodal"] if "confidence_multimodal" in work.columns else work["confidence"]
    confidence_threshold = (
        pd.to_numeric(work["policy_confidence_threshold"], errors="coerce").fillna(risk.confidence_threshold)
        if "policy_confidence_threshold" in work.columns
        else pd.Series(risk.confidence_threshold, index=work.index)
    )
    prob_up_threshold = (
        pd.to_numeric(work["policy_prob_up_threshold"], errors="coerce").fillna(risk.prob_up_threshold)
        if "policy_prob_up_threshold" in work.columns
        else pd.Series(risk.prob_up_threshold, index=work.index)
    )
    prob_down_threshold = (
        pd.to_numeric(work["policy_prob_down_threshold"], errors="coerce").fillna(risk.prob_down_threshold)
        if "policy_prob_down_threshold" in work.columns
        else pd.Series(risk.prob_down_threshold, index=work.index)
    )
    position_scale = (
        pd.to_numeric(work["bandit_position_scale"], errors="coerce").fillna(1.0).clip(0.35, 1.35)
        if "bandit_position_scale" in work.columns
        else pd.Series(1.0, index=work.index)
    )
    reward_risk_ratio = (
        pd.to_numeric(work["policy_reward_risk_ratio"], errors="coerce").fillna(risk.reward_risk_ratio).clip(1.8, 3.5)
        if "policy_reward_risk_ratio" in work.columns
        else pd.Series(risk.reward_risk_ratio, index=work.index)
    )

    signal = np.where(
        (confidence_series >= confidence_threshold)
        & (prob_series >= prob_up_threshold)
        & (work["predicted_return"] > 0),
        1,
        np.where(
            (confidence_series >= confidence_threshold)
            & (prob_series <= prob_down_threshold)
            & (work["predicted_return"] < 0),
            -1,
            0,
        ),
    )
    work["signal"] = signal
    work["signal_label"] = [signal_label(int(value)) for value in signal]
    work["prob_signal"] = prob_series
    work["confidence_signal"] = confidence_series
    work["position_scale"] = position_scale
    work["reward_risk_ratio_signal"] = reward_risk_ratio
    work["confidence_threshold_signal"] = confidence_threshold
    work["prob_up_threshold_signal"] = prob_up_threshold
    work["prob_down_threshold_signal"] = prob_down_threshold

    atr_stop = work["atr_14"].fillna(work["close"] * 0.012)
    atr_stop = atr_stop.where(atr_stop > 0, work["close"] * 0.012)
    work["entry_reference"] = work["close"]
    work["stop_loss"] = work["close"] - work["signal"] * atr_stop
    work["take_profit"] = work["close"] + work["signal"] * atr_stop * reward_risk_ratio
    return work


def run_backtest(signals: pd.DataFrame, risk: RiskConfig | None = None) -> tuple[pd.DataFrame, dict[str, float]]:
    risk = risk or RiskConfig()
    if signals.empty:
        return signals.copy(), {}

    work = signals.copy()
    stressed_threshold = work["ewma_vol_20"].quantile(risk.vol_reduce_quantile)
    work["stressed"] = work["ewma_vol_20"] >= stressed_threshold

    equity = risk.account_equity
    equity_history = []
    trades = []
    weekly_pnl_ratio: dict[pd.Timestamp, float] = {}
    halted = False

    for ts, row in work.iterrows():
        if halted or int(row["signal"]) == 0:
            equity_history.append(equity)
            continue

        position_scale = float(row.get("position_scale", row.get("bandit_position_scale", 1.0)) or 1.0)
        reward_risk_ratio = float(row.get("reward_risk_ratio_signal", row.get("policy_reward_risk_ratio", risk.reward_risk_ratio)) or risk.reward_risk_ratio)
        slippage_ticks = risk.stressed_slippage_ticks if row["stressed"] else risk.default_slippage_ticks
        stop_distance = abs(row["entry_reference"] - row["stop_loss"])
        risk_per_contract = max(stop_distance * risk.contract_size, row["entry_reference"] * 0.005)
        allowed_risk = equity * risk.single_trade_risk_pct * position_scale
        margin_per_contract = row["entry_reference"] * risk.contract_size * risk.default_margin_rate
        max_contracts_risk = int(max(0, allowed_risk // risk_per_contract))
        max_contracts_margin = int(max(0, (equity * risk.single_side_margin_pct) // margin_per_contract))
        contracts = max(0, min(max_contracts_risk, max_contracts_margin))

        if contracts == 0:
            equity_history.append(equity)
            continue

        raw_return = int(row["signal"]) * float(row["actual_return"])
        stop_return = stop_distance / row["entry_reference"]
        take_return = stop_return * reward_risk_ratio
        clipped_return = float(np.clip(raw_return, -stop_return, take_return))

        fee_cost = 2 * risk.default_fee_per_lot * contracts
        slippage_cost = 2 * slippage_ticks * risk.tick_size * risk.contract_size * contracts
        pnl = clipped_return * row["entry_reference"] * risk.contract_size * contracts - fee_cost - slippage_cost

        new_equity = equity + pnl
        iso_year, iso_week, _ = ts.isocalendar()
        week_key = pd.Timestamp.fromisocalendar(int(iso_year), int(iso_week), 1)
        weekly_pnl_ratio.setdefault(week_key, 0.0)
        weekly_pnl_ratio[week_key] += pnl / max(equity, 1.0)
        if weekly_pnl_ratio[week_key] <= -risk.weekly_circuit_breaker_pct:
            halted = True

        trades.append(
            {
                "date": ts,
                "signal": int(row["signal"]),
                "signal_label": row["signal_label"],
                "contracts": contracts,
                "entry_reference": row["entry_reference"],
                "stop_loss": row["stop_loss"],
                "take_profit": row["take_profit"],
                "confidence": row.get("confidence_signal", row["confidence"]),
                "prob_up": row.get("prob_signal", row["prob_up"]),
                "predicted_return": row["predicted_return"],
                "actual_return": row["actual_return"],
                "policy_action": row.get("bandit_action_label", row.get("bandit_action", "平衡")),
                "position_scale": position_scale,
                "reward_risk_ratio": reward_risk_ratio,
                "gross_return_clipped": clipped_return,
                "fee_cost": fee_cost,
                "slippage_cost": slippage_cost,
                "pnl": pnl,
                "equity_after": new_equity,
                "regime": row["regime"],
                "driver_summary": row["driver_summary"],
            }
        )
        equity = new_equity
        equity_history.append(equity)

    trade_frame = pd.DataFrame(trades).set_index("date") if trades else pd.DataFrame(columns=["pnl"])
    work = work.iloc[: len(equity_history)].copy()
    work["equity"] = pd.Series(equity_history, index=work.index)
    work["strategy_return"] = work["equity"].pct_change().fillna(0.0)
    metrics = compute_metrics(work["strategy_return"], trade_frame)
    return trade_frame, metrics


def compute_metrics(strategy_returns: pd.Series, trades: pd.DataFrame) -> dict[str, float]:
    returns = strategy_returns.fillna(0.0)
    if returns.empty:
        return {}

    equity = (1 + returns).cumprod()
    running_max = equity.cummax()
    drawdown = equity / running_max - 1

    annual_return = float(equity.iloc[-1] ** (252 / max(len(equity), 1)) - 1)
    annual_volatility = float(returns.std(ddof=1) * np.sqrt(252)) if len(returns) > 1 else 0.0
    downside = returns.where(returns < 0, 0.0)
    downside_volatility = float(downside.std(ddof=1) * np.sqrt(252)) if len(returns) > 1 else 0.0
    sharpe = float(returns.mean() / max(returns.std(ddof=1), 1e-8) * np.sqrt(252)) if len(returns) > 1 else 0.0
    sortino = float(returns.mean() / max(downside.std(ddof=1), 1e-8) * np.sqrt(252)) if len(returns) > 1 else 0.0
    max_drawdown = float(drawdown.min())
    calmar = float(annual_return / max(abs(max_drawdown), 1e-8))

    wins = trades[trades["pnl"] > 0]["pnl"] if not trades.empty else pd.Series(dtype=float)
    losses = trades[trades["pnl"] < 0]["pnl"] if not trades.empty else pd.Series(dtype=float)
    win_rate = float((trades["pnl"] > 0).mean()) if not trades.empty else 0.0
    avg_win = float(wins.mean()) if not wins.empty else 0.0
    avg_loss = float(losses.mean()) if not losses.empty else 0.0
    profit_factor = float(wins.sum() / max(abs(losses.sum()), 1e-8)) if not trades.empty else 0.0
    pnl = trades["pnl"] if not trades.empty and "pnl" in trades.columns else pd.Series(dtype=float)
    fee_cost = pd.to_numeric(trades.get("fee_cost", pd.Series(dtype=float)), errors="coerce").fillna(0.0) if not trades.empty else pd.Series(dtype=float)
    slippage_cost = pd.to_numeric(trades.get("slippage_cost", pd.Series(dtype=float)), errors="coerce").fillna(0.0) if not trades.empty else pd.Series(dtype=float)
    total_cost = fee_cost.add(slippage_cost, fill_value=0.0)
    expectancy = float(pnl.mean()) if not pnl.empty else 0.0
    payoff_ratio = float(abs(avg_win / avg_loss)) if avg_loss != 0 else 0.0
    high_conf = trades[pd.to_numeric(trades.get("confidence", 0.0), errors="coerce").fillna(0.0) >= 80] if not trades.empty and "confidence" in trades.columns else pd.DataFrame()
    avg_holding_period = 1.0 if not trades.empty else 0.0
    if not trades.empty and "contracts" in trades.columns and "entry_reference" in trades.columns:
        turnover = float((pd.to_numeric(trades["contracts"], errors="coerce").fillna(0.0).abs() * pd.to_numeric(trades["entry_reference"], errors="coerce").fillna(0.0)).sum() * 2.0)
    else:
        turnover = 0.0

    return {
        "cumulative_return": float(equity.iloc[-1] - 1),
        "annual_return": annual_return,
        "annual_volatility": annual_volatility,
        "downside_volatility": downside_volatility,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_drawdown": max_drawdown,
        "trade_count": float(0 if trades.empty else len(trades)),
        "win_rate": win_rate,
        "profit_factor": profit_factor,
        "avg_win": avg_win,
        "avg_loss": avg_loss,
        "reward_risk_ratio": payoff_ratio,
        "payoff_ratio": payoff_ratio,
        "expectancy": expectancy,
        "avg_holding_period": avg_holding_period,
        "turnover": turnover,
        "net_profit_after_cost": float(pnl.sum()) if not pnl.empty else 0.0,
        "break_even_cost": float(total_cost.sum()) if not total_cost.empty else 0.0,
        "high_conf_hit_rate": float((high_conf["pnl"] > 0).mean()) if not high_conf.empty and "pnl" in high_conf.columns else 0.0,
    }


def build_backtest_diagnostics(signals: pd.DataFrame, trades: pd.DataFrame, metrics: dict[str, float]) -> dict[str, object]:
    diagnostics: dict[str, object] = {
        "summary": metrics,
        "regime_rows": [],
        "monthly_rows": [],
        "rolling_rows": [],
        "quality": {},
    }
    if not isinstance(signals, pd.DataFrame) or signals.empty:
        return diagnostics

    work = signals.copy()
    prob = pd.to_numeric(work.get("prob_up_multimodal", work.get("prob_up", pd.Series(0.5, index=work.index))), errors="coerce").fillna(0.5)
    predicted_return = pd.to_numeric(work.get("predicted_return", pd.Series(0.0, index=work.index)), errors="coerce").fillna(0.0)
    actual_return = pd.to_numeric(work.get("actual_return", pd.Series(0.0, index=work.index)), errors="coerce").fillna(0.0)
    direction_active = (prob.sub(0.5).abs() >= 0.055) | (predicted_return.abs() >= 0.002)
    direction_hit = ((prob >= 0.5) & (actual_return >= 0)) | ((prob < 0.5) & (actual_return < 0))
    center_error = actual_return - predicted_return
    work["direction_active_bt"] = direction_active.astype(float)
    work["direction_hit_bt"] = direction_hit.astype(float).where(direction_active)
    work["abs_error_bt"] = center_error.abs()
    if "direction_calibration_hit_rate" in work.columns:
        work["direction_learning_quality"] = pd.to_numeric(work["direction_calibration_hit_rate"], errors="coerce")
    else:
        work["direction_learning_quality"] = work["direction_hit_bt"].fillna(0.5)

    if "regime" in work.columns:
        regime_rows = []
        for regime, group in work.groupby("regime"):
            regime_rows.append(
                {
                    "regime": str(regime),
                    "sample_count": int(len(group)),
                    "direction_active_rate": float(group["direction_active_bt"].mean()),
                    "direction_hit_rate": float(group["direction_hit_bt"].dropna().mean()) if group["direction_hit_bt"].notna().any() else 0.5,
                    "direction_learning_quality": float(group["direction_learning_quality"].dropna().mean()),
                    "avg_abs_error": float(group["abs_error_bt"].mean()),
                    "avg_confidence": float(pd.to_numeric(group.get("confidence_multimodal", group.get("confidence", 0.0)), errors="coerce").mean()),
                }
            )
        diagnostics["regime_rows"] = sorted(regime_rows, key=lambda row: row["sample_count"], reverse=True)

    rolling_rows = []
    for window in (20, 60, 120):
        if len(work) >= window:
            recent = work.tail(window)
            rolling_rows.append(
                {
                    "window": window,
                    "direction_active_rate": float(recent["direction_active_bt"].mean()),
                    "neutral_rate": float(1.0 - recent["direction_active_bt"].mean()),
                    "direction_hit_rate": float(recent["direction_hit_bt"].dropna().mean()) if recent["direction_hit_bt"].notna().any() else 0.5,
                    "direction_learning_quality": float(recent["direction_learning_quality"].dropna().mean()),
                    "avg_abs_error": float(recent["abs_error_bt"].mean()),
                    "signal_rate": float((pd.to_numeric(recent.get("signal", 0), errors="coerce").fillna(0) != 0).mean()),
                }
            )
    diagnostics["rolling_rows"] = rolling_rows

    if isinstance(trades, pd.DataFrame) and not trades.empty:
        trade_work = trades.copy()
        trade_work.index = pd.to_datetime(trade_work.index, errors="coerce")
        monthly = []
        for month, group in trade_work.groupby(trade_work.index.to_period("M")):
            wins = group[group["pnl"] > 0]["pnl"]
            losses = group[group["pnl"] < 0]["pnl"]
            monthly.append(
                {
                    "month": str(month),
                    "trade_count": int(len(group)),
                    "win_rate": float((group["pnl"] > 0).mean()),
                    "pnl": float(group["pnl"].sum()),
                    "profit_factor": float(wins.sum() / max(abs(losses.sum()), 1e-8)) if not losses.empty else float("inf") if not wins.empty else 0.0,
                }
            )
        diagnostics["monthly_rows"] = monthly[-18:]
        diagnostics["quality"] = {
            "avg_trade_pnl": float(trade_work["pnl"].mean()),
            "median_trade_pnl": float(trade_work["pnl"].median()),
            "pnl_stability": float(max(0.0, min(1.0, 1.0 - abs(pd.Series([row["pnl"] for row in monthly]).std(ddof=1) / max(abs(pd.Series([row["pnl"] for row in monthly]).mean()), 1e-8))))) if len(monthly) > 1 else 0.5,
            "latest_10_trade_win_rate": float((trade_work.tail(10)["pnl"] > 0).mean()) if len(trade_work) >= 3 else 0.0,
        }
    return diagnostics
