from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


DEFAULT_HORIZONS = ("1d", "3d", "5d", "10d", "20d")


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


def _optimizer_dir(candidate_version: str) -> Path:
    path = _output_dir() / "model_research" / "strategy_optimization" / _normalise_version(candidate_version)
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_oof(candidate_version: str, horizon: str) -> pd.DataFrame:
    path = _trace_path(candidate_version, horizon)
    if not path.exists():
        return pd.DataFrame()
    frame = pd.read_csv(path)
    if frame.empty:
        return frame
    frame["fold_id"] = frame.get("fold_id", "").astype(str)
    return frame


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _evaluate(frame: pd.DataFrame, *, min_confidence: float, min_trade_edge: float, cost_multiplier: float = 1.0) -> dict[str, Any]:
    if frame.empty:
        return {"sample_count": 0, "trade_count": 0, "expectancy": 0.0, "accuracy": 0.0, "max_drawdown": 0.0}
    predicted = pd.to_numeric(frame.get("predicted_direction", 0), errors="coerce").fillna(0).astype(int)
    realized_dir = pd.to_numeric(frame.get("realized_direction", 0), errors="coerce").fillna(0).astype(int)
    realized_ret = pd.to_numeric(frame.get("realized_return", 0.0), errors="coerce").fillna(0.0).astype(float)
    confidence = pd.to_numeric(frame.get("confidence", 0.0), errors="coerce").fillna(0.0).astype(float)
    edge = pd.to_numeric(frame.get("trade_edge", 0.0), errors="coerce").fillna(0.0).astype(float)
    cost = pd.to_numeric(frame.get("cost_assumption", 0.0002), errors="coerce").fillna(0.0002).astype(float) * float(cost_multiplier)
    selected = (predicted != 0) & (confidence >= float(min_confidence)) & (edge >= float(min_trade_edge))
    returns = np.where(selected, np.sign(predicted) * realized_ret - cost, 0.0)
    equity = np.cumsum(returns)
    peak = np.maximum.accumulate(equity) if len(equity) else np.asarray([], dtype=float)
    drawdown = equity - peak if len(equity) else np.asarray([], dtype=float)
    selected_count = int(selected.sum())
    accuracy = float((np.sign(predicted[selected]) == np.sign(realized_dir[selected])).mean()) if selected_count else 0.0
    return {
        "sample_count": int(len(frame)),
        "trade_count": selected_count,
        "coverage": float(selected_count / max(len(frame), 1)),
        "accuracy": accuracy,
        "expectancy": float(np.mean(returns[selected])) if selected_count else 0.0,
        "max_drawdown": float(np.min(drawdown)) if len(drawdown) else 0.0,
        "cost_multiplier": float(cost_multiplier),
    }


def _fold_sort_key(value: str) -> tuple[int, str]:
    try:
        return int(float(value)), value
    except Exception:
        return 10**9, value


def optimize_research_strategy(
    *,
    candidate_version: str = "v3",
    horizons: Iterable[str] = DEFAULT_HORIZONS,
    confidence_grid: Iterable[float] = (0.55, 0.60, 0.65, 0.70, 0.75),
    edge_grid: Iterable[float] = (0.0, 0.0002, 0.0005, 0.0010),
) -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    out = _optimizer_dir(version)
    trial_rows: list[dict[str, Any]] = []
    best_by_horizon: dict[str, Any] = {}

    for horizon in horizons:
        h = str(horizon)
        frame = _read_oof(version, h)
        if frame.empty or "fold_id" not in frame.columns:
            best_by_horizon[h] = {"status": "missing_oof_trace", "trace_path": str(_trace_path(version, h))}
            continue
        folds = sorted([str(value) for value in frame["fold_id"].dropna().astype(str).unique()], key=_fold_sort_key)
        horizon_trials: list[dict[str, Any]] = []
        for fold in folds:
            prior_folds = [item for item in folds if _fold_sort_key(item) < _fold_sort_key(fold)]
            if not prior_folds:
                continue
            train = frame.loc[frame["fold_id"].astype(str).isin(prior_folds)]
            validation = frame.loc[frame["fold_id"].astype(str) == fold]
            best_train: dict[str, Any] | None = None
            for confidence in confidence_grid:
                for edge in edge_grid:
                    train_metrics = _evaluate(train, min_confidence=float(confidence), min_trade_edge=float(edge))
                    if best_train is None or (
                        train_metrics["expectancy"],
                        train_metrics["trade_count"],
                        train_metrics["accuracy"],
                    ) > (
                        best_train["train_expectancy"],
                        best_train["train_trade_count"],
                        best_train["train_accuracy"],
                    ):
                        best_train = {
                            "min_confidence": float(confidence),
                            "min_trade_edge": float(edge),
                            "train_expectancy": train_metrics["expectancy"],
                            "train_accuracy": train_metrics["accuracy"],
                            "train_trade_count": train_metrics["trade_count"],
                        }
            if best_train is None:
                continue
            val_metrics = _evaluate(
                validation,
                min_confidence=float(best_train["min_confidence"]),
                min_trade_edge=float(best_train["min_trade_edge"]),
            )
            row = {
                "candidate_version": version,
                "horizon": h,
                "validation_fold": fold,
                "trained_on_folds": "|".join(prior_folds),
                **best_train,
                **{f"validation_{key}": value for key, value in val_metrics.items()},
                "active_updated": False,
                "customer_prediction_generated": False,
            }
            trial_rows.append(row)
            horizon_trials.append(row)
        if horizon_trials:
            best_by_horizon[h] = max(
                horizon_trials,
                key=lambda item: (
                    _safe_float(item.get("validation_expectancy")),
                    _safe_float(item.get("validation_trade_count")),
                    _safe_float(item.get("validation_accuracy")),
                ),
            )
            best_by_horizon[h]["status"] = "success"
        else:
            best_by_horizon[h] = {"status": "insufficient_folds", "message_zh": "OOF folds 不足，未做阈值优化。"}

    all_trials_path = out / "all_trials.csv"
    pd.DataFrame(trial_rows).to_csv(all_trials_path, index=False, encoding="utf-8")
    report = {
        "status": "success" if trial_rows else "not_enough_data",
        "candidate_version": version,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "best_by_horizon": best_by_horizon,
        "all_trials_path": str(all_trials_path),
        "optimization_policy": "thresholds selected on earlier folds only; validation folds are evaluation-only",
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "sample_data_used": False,
    }
    report_path = out / "optimization_report.json"
    _write_json(report_path, report)
    report["report_path"] = str(report_path)
    return sanitize_for_json(report)


def get_strategy_optimization_report(*, candidate_version: str = "v3") -> dict[str, Any]:
    path = _optimizer_dir(candidate_version) / "optimization_report.json"
    if not path.exists():
        return {"status": "not_run", "path": str(path), "message_zh": "策略优化尚未运行。"}
    try:
        return sanitize_for_json(json.loads(path.read_text(encoding="utf-8")))
    except Exception:
        return {"status": "failed", "path": str(path), "message_zh": "策略优化报告无法读取。"}

