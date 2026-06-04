from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .institutional_validation_service import deflated_sharpe_ratio, probability_of_backtest_overfitting, white_reality_check
from .research_strategy_optimizer import DEFAULT_HORIZONS, optimize_research_strategy


OBJECTIVES = {
    "maximize": ["cost_adjusted_expectancy", "top20_accuracy", "deflated_sharpe_ratio", "feature_stability"],
    "minimize": ["max_drawdown", "probability_of_backtest_overfitting", "turnover", "concentration_risk"],
}
CONSTRAINTS = {
    "no_mock_data_for_promotion": True,
    "no_sample_data": True,
    "2x_cost_stress_non_negative": True,
    "worst_fold_threshold": 0.52,
    "worst_regime_threshold": 0.50,
    "high_confidence_sample_count_threshold": 30,
}


def _output_dir() -> Path:
    return get_user_output_dir()


def _normalise_version(version: str | None) -> str:
    value = str(version or "v5").strip().lower()
    return value or "v5"


def _trace_path(candidate_version: str, horizon: str) -> Path:
    version = _normalise_version(candidate_version)
    base = _output_dir() / "walk_forward"
    if version != "v1":
        base = base / version
    return base / f"oof_trace_{horizon}.csv"


def _optimizer_dir(candidate_version: str) -> Path:
    path = _output_dir() / "model_research" / "multi_objective_optimization" / _normalise_version(candidate_version)
    path.mkdir(parents=True, exist_ok=True)
    return path


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
    frame["fold_id"] = frame.get("fold_id", "").astype(str)
    return frame


def _evaluate(frame: pd.DataFrame, *, min_confidence: float = 0.0, min_trade_edge: float = 0.0, cost_multiplier: float = 1.0) -> dict[str, Any]:
    if frame.empty:
        return {
            "sample_count": 0,
            "trade_count": 0,
            "coverage": 0.0,
            "accuracy": 0.0,
            "expectancy": 0.0,
            "max_drawdown": 0.0,
            "turnover": 0.0,
        }
    predicted = pd.to_numeric(frame.get("predicted_direction", 0), errors="coerce").fillna(0).astype(int)
    realized_dir = pd.to_numeric(frame.get("realized_direction", 0), errors="coerce").fillna(0).astype(int)
    realized_ret = pd.to_numeric(frame.get("realized_return", 0.0), errors="coerce").fillna(0.0).astype(float)
    confidence = pd.to_numeric(frame.get("confidence", 0.0), errors="coerce").fillna(0.0).astype(float)
    edge = pd.to_numeric(frame.get("trade_edge", 0.0), errors="coerce").fillna(0.0).astype(float)
    cost = pd.to_numeric(frame.get("cost_assumption", 0.0002), errors="coerce").fillna(0.0002).astype(float) * float(cost_multiplier)
    selected = (predicted != 0) & (confidence >= min_confidence) & (edge >= min_trade_edge)
    strategy_return = np.where(selected, np.sign(predicted) * realized_ret - cost, 0.0)
    equity = np.cumsum(strategy_return)
    peak = np.maximum.accumulate(equity) if equity.size else np.asarray([], dtype=float)
    drawdown = equity - peak if equity.size else np.asarray([], dtype=float)
    trade_count = int(selected.sum())
    accuracy = float((np.sign(predicted[selected]) == np.sign(realized_dir[selected])).mean()) if trade_count else 0.0
    expectancy = float(np.mean(strategy_return[selected])) if trade_count else 0.0
    return {
        "sample_count": int(len(frame)),
        "trade_count": trade_count,
        "coverage": float(trade_count / max(len(frame), 1)),
        "accuracy": accuracy,
        "expectancy": expectancy,
        "max_drawdown": float(np.min(drawdown)) if drawdown.size else 0.0,
        "turnover": float(trade_count / max(len(frame), 1)),
    }


def _top20(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty or "confidence" not in frame.columns:
        return frame.iloc[0:0].copy()
    confidence = pd.to_numeric(frame["confidence"], errors="coerce").fillna(0.0)
    cutoff = confidence.quantile(0.80)
    return frame.loc[confidence >= cutoff].copy()


def _worst_group_accuracy(frame: pd.DataFrame, group_col: str) -> float:
    if frame.empty or group_col not in frame.columns:
        return 0.0
    values: list[float] = []
    for _, group in frame.groupby(group_col):
        values.append(_evaluate(group)["accuracy"])
    return min(values) if values else 0.0


def _concentration(frame: pd.DataFrame, group_col: str) -> float:
    if frame.empty or group_col not in frame.columns:
        return 1.0
    counts = frame[group_col].astype(str).value_counts()
    return float(counts.max() / max(int(counts.sum()), 1)) if len(counts) else 1.0


def optimize_multi_objective_research_strategy(
    *,
    candidate_version: str = "v5",
    horizons: Iterable[str] = DEFAULT_HORIZONS,
) -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    out = _optimizer_dir(version)
    threshold_report = optimize_research_strategy(candidate_version=version, horizons=horizons)
    horizon_reports: dict[str, Any] = {}
    blocking_reasons: set[str] = set()
    pbo_inputs: dict[str, list[float]] = {}

    for horizon in horizons:
        h = str(horizon)
        frame = _read_oof(version, h)
        if frame.empty:
            horizon_reports[h] = {"status": "missing_oof_trace", "trace_path": str(_trace_path(version, h))}
            blocking_reasons.add("missing_oof_trace")
            continue
        top20 = _top20(frame)
        full = _evaluate(frame)
        top20_metrics = _evaluate(top20)
        cost2 = _evaluate(top20, cost_multiplier=2.0)
        cost3 = _evaluate(top20, cost_multiplier=3.0)
        returns = []
        if not top20.empty:
            predicted = pd.to_numeric(top20.get("predicted_direction", 0), errors="coerce").fillna(0).astype(int)
            realized = pd.to_numeric(top20.get("realized_return", 0.0), errors="coerce").fillna(0.0)
            returns = list((np.sign(predicted) * realized).astype(float))
        pbo_inputs[h] = returns
        dsr = deflated_sharpe_ratio(returns, trials=max(1, len(list(horizons))))
        reality = white_reality_check(returns)
        worst_fold = _worst_group_accuracy(top20, "fold_id")
        worst_regime = _worst_group_accuracy(top20, "regime_label")
        fold_concentration = _concentration(top20, "fold_id")
        regime_concentration = _concentration(top20, "regime_label")
        if cost2["expectancy"] < 0:
            blocking_reasons.add("2x_cost_stress_negative")
        if worst_fold < CONSTRAINTS["worst_fold_threshold"]:
            blocking_reasons.add("worst_fold_below_threshold")
        if worst_regime < CONSTRAINTS["worst_regime_threshold"]:
            blocking_reasons.add("worst_regime_below_threshold")
        if top20_metrics["trade_count"] < CONSTRAINTS["high_confidence_sample_count_threshold"]:
            blocking_reasons.add("insufficient_high_confidence_samples")
        horizon_reports[h] = {
            "status": "success",
            "full": full,
            "top20": top20_metrics,
            "cost_stress": {"2x": cost2, "3x": cost3},
            "deflated_sharpe_ratio": dsr,
            "reality_check": reality,
            "worst_fold_accuracy": worst_fold,
            "worst_regime_accuracy": worst_regime,
            "fold_concentration": fold_concentration,
            "regime_concentration": regime_concentration,
        }

    pbo = probability_of_backtest_overfitting(pbo_inputs)
    if _safe_float(pbo.get("pbo"), 1.0) > 0.20:
        blocking_reasons.add("pbo_above_threshold")
    promotion_readiness = "eligible_for_manual_review" if not blocking_reasons else "research_only"

    all_trials_path = out / "all_trials.csv"
    source_trials = Path(str(threshold_report.get("all_trials_path") or ""))
    if source_trials.exists():
        all_trials_path.write_text(source_trials.read_text(encoding="utf-8"), encoding="utf-8")
    else:
        pd.DataFrame().to_csv(all_trials_path, index=False, encoding="utf-8")

    report = {
        "status": "success" if horizon_reports else "not_enough_data",
        "candidate_version": version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "objectives": OBJECTIVES,
        "constraints": CONSTRAINTS,
        "horizons": horizon_reports,
        "pbo": pbo,
        "blocking_reasons": sorted(blocking_reasons),
        "promotion_readiness": promotion_readiness,
        "all_trials_path": str(all_trials_path),
        "threshold_optimizer_report": threshold_report.get("report_path"),
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "sample_data_used": False,
        "message_zh": "Multi-objective research optimization completed for candidate only; no active model or customer prediction was generated.",
    }
    report_path = out / "optimization_report.json"
    _write_json(report_path, report)
    report["report_path"] = str(report_path)
    return sanitize_for_json(report)
