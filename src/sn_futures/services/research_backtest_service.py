from __future__ import annotations

import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .institutional_validation_service import (
    deflated_sharpe_ratio,
    probability_of_backtest_overfitting,
    white_reality_check,
)


DEFAULT_HORIZONS = ("1d", "3d", "5d", "10d", "20d")
DEFAULT_COST = 0.0002
DEFAULT_SLIPPAGE = 0.0001


def _output_dir() -> Path:
    return get_user_output_dir()


def _normalise_version(version: str | None) -> str:
    value = str(version or "v3").strip().lower()
    return value or "v3"


def _trace_path(candidate_version: str, horizon: str) -> Path:
    version = _normalise_version(candidate_version)
    base = _output_dir() / "walk_forward"
    if version != "v1":
        base = base / version
    return base / f"oof_trace_{horizon}.csv"


def _backtest_dir(candidate_version: str) -> Path:
    path = _output_dir() / "research_backtests" / _normalise_version(candidate_version)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _read_oof(candidate_version: str, horizon: str) -> pd.DataFrame:
    path = _trace_path(candidate_version, horizon)
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if frame.empty:
        return frame
    for col in ("timestamp", "label_start_time", "label_end_time"):
        if col in frame.columns:
            frame[col] = pd.to_datetime(frame[col], errors="coerce")
    return frame.sort_values([col for col in ("label_start_time", "timestamp") if col in frame.columns]).reset_index(drop=True)


def _strategy_frame(frame: pd.DataFrame, *, cost_multiplier: float = 1.0) -> pd.DataFrame:
    work = frame.copy()
    if work.empty:
        return work
    predicted = pd.to_numeric(work.get("predicted_direction", 0), errors="coerce").fillna(0).astype(int)
    realized = pd.to_numeric(work.get("realized_return", 0.0), errors="coerce").fillna(0.0).astype(float)
    confidence = pd.to_numeric(work.get("confidence", 0.0), errors="coerce").fillna(0.0).astype(float)
    edge = pd.to_numeric(work.get("trade_edge", 0.0), errors="coerce").fillna(0.0).astype(float)
    cost = pd.to_numeric(work.get("cost_assumption", DEFAULT_COST), errors="coerce").fillna(DEFAULT_COST).astype(float)
    selected = (predicted != 0) & (confidence >= 0.0) & (edge > 0.0)
    work["position"] = np.where(selected, np.sign(predicted), 0).astype(int)
    work["cost"] = np.where(selected, cost * float(cost_multiplier), 0.0)
    work["slippage"] = np.where(selected, DEFAULT_SLIPPAGE * float(cost_multiplier), 0.0)
    work["gross_return"] = work["position"] * realized
    work["strategy_return"] = work["gross_return"] - work["cost"] - work["slippage"]
    # OOF samples can overlap for multi-day horizons, so use a linear research
    # curve rather than compounding every validation sample as an independent
    # executable trade.
    work["equity"] = 1.0 + work["strategy_return"].cumsum()
    peak = work["equity"].cummax()
    work["drawdown"] = work["equity"] / peak - 1.0
    work["is_trade"] = selected
    return work


def _annual_factor(horizon: str) -> float:
    days = 1
    try:
        days = max(1, int(str(horizon).lower().replace("d", "")))
    except Exception:
        pass
    return 252.0 / float(days)


def _metrics(strategy: pd.DataFrame, horizon: str, *, cost_multiplier: float = 1.0) -> dict[str, Any]:
    if strategy.empty:
        return {
            "status": "empty",
            "horizon": horizon,
            "signal_source": "oof_trace_only",
            "trade_count": 0,
            "total_return": 0.0,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    returns = pd.to_numeric(strategy["strategy_return"], errors="coerce").fillna(0.0).to_numpy(dtype=float)
    trades = strategy.loc[strategy["is_trade"]].copy()
    trade_returns = pd.to_numeric(trades.get("strategy_return", pd.Series(dtype=float)), errors="coerce").fillna(0.0).to_numpy(dtype=float)
    total_return = float(strategy["equity"].iloc[-1] - 1.0) if "equity" in strategy else float(np.sum(returns))
    periods = max(len(strategy), 1)
    ann_factor = _annual_factor(horizon)
    annual_return = float((1.0 + total_return) ** (ann_factor / periods) - 1.0) if total_return > -1.0 else -1.0
    std = float(np.std(returns, ddof=1)) if len(returns) > 1 else 0.0
    downside = returns[returns < 0]
    downside_std = float(np.std(downside, ddof=1)) if len(downside) > 1 else 0.0
    sharpe = float(np.mean(returns) / std * math.sqrt(ann_factor)) if std > 1e-12 else 0.0
    sortino = float(np.mean(returns) / downside_std * math.sqrt(ann_factor)) if downside_std > 1e-12 else 0.0
    max_dd = float(strategy["drawdown"].min()) if "drawdown" in strategy and len(strategy) else 0.0
    calmar = float(annual_return / abs(max_dd)) if abs(max_dd) > 1e-12 else 0.0
    wins = trade_returns[trade_returns > 0]
    losses = trade_returns[trade_returns < 0]
    profit_factor = float(wins.sum() / abs(losses.sum())) if abs(losses.sum()) > 1e-12 else (float("inf") if wins.size else 0.0)
    reality = white_reality_check(trade_returns if trade_returns.size else returns)
    pbo = probability_of_backtest_overfitting({horizon: trade_returns if trade_returns.size else returns, f"{horizon}_all": returns})
    dsr = deflated_sharpe_ratio(trade_returns if trade_returns.size else returns, trials=1)
    return sanitize_for_json(
        {
            "status": "success",
            "horizon": horizon,
            "cost_multiplier": float(cost_multiplier),
            "signal_source": "oof_trace_only",
            "sample_count": int(len(strategy)),
            "trade_count": int(len(trades)),
            "total_return": total_return,
            "annual_return": annual_return,
            "sharpe": sharpe,
            "sortino": sortino,
            "calmar": calmar,
            "max_drawdown": max_dd,
            "win_rate": float((trade_returns > 0).mean()) if trade_returns.size else 0.0,
            "profit_factor": profit_factor,
            "expectancy": float(np.mean(trade_returns)) if trade_returns.size else 0.0,
            "turnover": float(len(trades) / max(len(strategy), 1)),
            "cost_total": float(strategy["cost"].sum()) if "cost" in strategy else 0.0,
            "slippage_total": float(strategy["slippage"].sum()) if "slippage" in strategy else 0.0,
            "equity_curve_method": "linear_oof_sum_no_overlap_compounding",
            "deflated_sharpe_ratio": dsr,
            "probability_of_backtest_overfitting": pbo,
            "reality_check_p_value": reality.get("p_value"),
            "research_only": True,
            "sample_data_used": False,
            "baseline_used": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        }
    )


def _write_horizon_outputs(candidate_version: str, horizon: str, strategy: pd.DataFrame) -> dict[str, Any]:
    out = _backtest_dir(candidate_version)
    equity_path = out / f"equity_curve_{horizon}.csv"
    drawdown_path = out / f"drawdown_curve_{horizon}.csv"
    trades_path = out / f"trades_{horizon}.csv"
    metrics_path = out / f"metrics_{horizon}.json"
    equity_cols = [col for col in ("timestamp", "label_start_time", "label_end_time", "strategy_return", "equity", "position", "confidence", "trade_edge") if col in strategy.columns]
    drawdown_cols = [col for col in ("timestamp", "label_start_time", "equity", "drawdown") if col in strategy.columns]
    trade_cols = [col for col in ("timestamp", "label_start_time", "label_end_time", "position", "realized_return", "strategy_return", "confidence", "trade_edge", "regime_label") if col in strategy.columns]
    strategy[equity_cols].to_csv(equity_path, index=False, encoding="utf-8")
    strategy[drawdown_cols].to_csv(drawdown_path, index=False, encoding="utf-8")
    strategy.loc[strategy["is_trade"], trade_cols].to_csv(trades_path, index=False, encoding="utf-8")
    metrics = _metrics(strategy, horizon)
    metrics["cost_stress"] = {
        "2x_cost": _metrics(_strategy_frame(strategy, cost_multiplier=2.0), horizon, cost_multiplier=2.0),
        "3x_cost": _metrics(_strategy_frame(strategy, cost_multiplier=3.0), horizon, cost_multiplier=3.0),
    }
    _write_json(metrics_path, metrics)
    return sanitize_for_json(
        {
            "horizon": horizon,
            "status": "success",
            "equity_curve_path": str(equity_path),
            "drawdown_curve_path": str(drawdown_path),
            "trades_path": str(trades_path),
            "metrics_path": str(metrics_path),
            "metrics": metrics,
        }
    )


def _write_report(candidate_version: str, horizons: Mapping[str, Mapping[str, Any]]) -> str:
    path = _backtest_dir(candidate_version) / "research_backtest_report.md"
    lines = [
        f"# Candidate {candidate_version} Research Backtest",
        "",
        "研究回测，不代表 live active 预测，不构成投资建议。",
        "",
        "All signals are out-of-fold validation traces. No active model was published and no customer prediction was generated.",
        "",
        "| Horizon | Trade Count | Total Return | Max Drawdown | Sharpe | Expectancy |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for horizon, payload in horizons.items():
        metrics = payload.get("metrics") if isinstance(payload, Mapping) else {}
        if not isinstance(metrics, Mapping):
            metrics = {}
        lines.append(
            f"| {horizon} | {metrics.get('trade_count', 0)} | {float(metrics.get('total_return') or 0.0):.6f} | "
            f"{float(metrics.get('max_drawdown') or 0.0):.6f} | {float(metrics.get('sharpe') or 0.0):.6f} | "
            f"{float(metrics.get('expectancy') or 0.0):.6f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return str(path)


def run_research_backtest(
    *,
    candidate_version: str = "v3",
    horizons: Iterable[str] = DEFAULT_HORIZONS,
    cost_config: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    horizon_results: dict[str, Any] = {}
    for horizon in horizons:
        h = str(horizon)
        trace = _read_oof(version, h)
        if trace.empty:
            horizon_results[h] = {
                "horizon": h,
                "status": "missing_oof_trace",
                "message_zh": "未找到该周期 OOF 样本外轨迹，未生成研究回测。",
                "trace_path": str(_trace_path(version, h)),
            }
            continue
        strategy = _strategy_frame(trace, cost_multiplier=_safe_float((cost_config or {}).get("cost_multiplier"), 1.0))
        horizon_results[h] = _write_horizon_outputs(version, h, strategy)
    report_path = _write_report(version, horizon_results)
    status = "success" if any(item.get("status") == "success" for item in horizon_results.values() if isinstance(item, Mapping)) else "failed"
    payload = {
        "status": status,
        "candidate_version": version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "horizons": horizon_results,
        "report_path": report_path,
        "message_zh": "研究型回测已基于 OOF 样本外信号生成；未发布 active，未生成客户预测。",
        "research_only": True,
        "sample_data_used": False,
        "baseline_used": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    _write_json(_backtest_dir(version) / "research_backtest_status.json", payload)
    return sanitize_for_json(payload)


def get_research_backtest_report(*, run_id: str | None = None, candidate_version: str = "v3") -> dict[str, Any]:
    if run_id:
        path = _output_dir() / "research_runs" / Path(run_id).name / "research_backtest_report.md"
    else:
        path = _backtest_dir(candidate_version) / "research_backtest_report.md"
    if not path.exists():
        return {"status": "not_found", "markdown": "", "path": str(path), "message_zh": "研究型回测报告尚未生成。"}
    return {"status": "success", "path": str(path), "markdown": path.read_text(encoding="utf-8"), "message_zh": "研究型回测报告已生成。"}


def get_research_equity_curve(*, run_id: str | None = None, horizon: str = "1d", candidate_version: str = "v3") -> dict[str, Any]:
    if run_id:
        path = _output_dir() / "research_runs" / Path(run_id).name / f"equity_curve_{horizon}.csv"
    else:
        path = _backtest_dir(candidate_version) / f"equity_curve_{horizon}.csv"
    if not path.exists():
        return {"status": "not_found", "points": [], "path": str(path), "message_zh": "研究收益曲线尚未生成。"}
    frame = pd.read_csv(path)
    return {
        "status": "success",
        "path": str(path),
        "horizon": horizon,
        "points": sanitize_for_json(frame.to_dict(orient="records")),
        "message_zh": "研究收益曲线来自 OOF 样本外轨迹，不是客户预测。",
    }
