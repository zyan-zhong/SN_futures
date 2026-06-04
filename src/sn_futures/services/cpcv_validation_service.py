from __future__ import annotations

import itertools
import json
import math
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


DEFAULT_STRATEGY_COLUMNS = ("model_signal", "selected_signal_numeric", "top10_signal", "top20_signal")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _validation_dir() -> Path:
    path = get_user_output_dir() / "validation" / "cpcv"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_path() -> Path:
    return _validation_dir() / "cpcv_report.json"


def _group_indices(sample_count: int, n_groups: int) -> list[list[int]]:
    if sample_count <= 0:
        return []
    n_groups = max(2, min(int(n_groups), int(sample_count)))
    indices = np.arange(sample_count)
    return [list(map(int, chunk)) for chunk in np.array_split(indices, n_groups) if len(chunk)]


def build_cpcv_splits(
    *,
    sample_count: int,
    n_groups: int = 6,
    test_group_count: int = 2,
    purge: int = 1,
    embargo: int = 1,
) -> list[dict[str, Any]]:
    groups = _group_indices(int(sample_count), int(n_groups))
    if not groups:
        return []
    test_group_count = max(1, min(int(test_group_count), len(groups) - 1))
    purge = max(0, int(purge))
    embargo = max(0, int(embargo))
    all_indices = set(range(int(sample_count)))
    splits: list[dict[str, Any]] = []
    for path_idx, group_ids in enumerate(itertools.combinations(range(len(groups)), test_group_count), start=1):
        test_indices = sorted(idx for group_id in group_ids for idx in groups[group_id])
        blocked: set[int] = set(test_indices)
        purged: set[int] = set()
        embargoed: set[int] = set()
        for idx in test_indices:
            for blocked_idx in range(max(0, idx - purge), min(int(sample_count), idx + embargo + 1)):
                if blocked_idx < idx:
                    purged.add(blocked_idx)
                elif blocked_idx > idx:
                    embargoed.add(blocked_idx)
                blocked.add(blocked_idx)
        train_indices = sorted(all_indices - blocked)
        splits.append(
            {
                "path_id": f"cpcv_path_{path_idx:03d}",
                "mode": "cpcv_like_combinatorial_purged",
                "sample_count": int(sample_count),
                "n_groups": len(groups),
                "test_groups": [int(item) for item in group_ids],
                "test_indices": test_indices,
                "train_indices": train_indices,
                "purged_indices": sorted(purged),
                "embargo_indices": sorted(embargoed),
                "purge": purge,
                "embargo": embargo,
                "no_overlap": set(test_indices).isdisjoint(set(train_indices)),
                "purge_embargo_applied": bool(purge or embargo),
                "group_ranges": [
                    {
                        "group": idx,
                        "start_index": int(values[0]),
                        "end_index": int(values[-1]),
                        "sample_count": len(values),
                    }
                    for idx, values in enumerate(groups)
                ],
            }
        )
    return sanitize_for_json(splits)


def _strategy_returns(frame: pd.DataFrame, strategy_column: str, return_col: str, cost: float) -> pd.Series:
    signal = pd.to_numeric(frame[strategy_column], errors="coerce").fillna(0.0)
    realized = pd.to_numeric(frame[return_col], errors="coerce").fillna(0.0)
    traded = signal.abs() > 1e-12
    return signal * realized - traded.astype(float) * float(cost)


def compute_path_metrics(
    frame: pd.DataFrame,
    splits: Sequence[Mapping[str, Any]],
    *,
    strategy_columns: Sequence[str],
    return_col: str = "y_return",
    cost: float = 0.0,
) -> list[dict[str, Any]]:
    if return_col not in frame.columns:
        raise ValueError(f"missing return column: {return_col}")
    strategies = [str(col) for col in strategy_columns if str(col) in frame.columns]
    if not strategies:
        raise ValueError("no strategy columns available for CPCV metrics")
    rows: list[dict[str, Any]] = []
    clean = frame.reset_index(drop=True).copy()
    for split in splits:
        train_idx = [int(idx) for idx in split.get("train_indices", []) if 0 <= int(idx) < len(clean)]
        test_idx = [int(idx) for idx in split.get("test_indices", []) if 0 <= int(idx) < len(clean)]
        metrics: dict[str, dict[str, Any]] = {}
        for strategy in strategies:
            returns = _strategy_returns(clean, strategy, return_col, cost)
            train_returns = returns.iloc[train_idx].dropna()
            test_returns = returns.iloc[test_idx].dropna()
            metrics[strategy] = {
                "train_metric": float(train_returns.mean()) if len(train_returns) else 0.0,
                "test_metric": float(test_returns.mean()) if len(test_returns) else 0.0,
                "train_sample_count": int(len(train_returns)),
                "test_sample_count": int(len(test_returns)),
                "test_returns": [float(item) for item in test_returns.tolist()],
            }
        rows.append(
            {
                "path_id": str(split.get("path_id") or f"path_{len(rows) + 1}"),
                "test_groups": list(split.get("test_groups", [])),
                "train_sample_count": len(train_idx),
                "test_sample_count": len(test_idx),
                "strategy_metrics": metrics,
                "research_only": True,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
        )
    return sanitize_for_json(rows)


def _selected_strategy(path_metric: Mapping[str, Any]) -> str:
    explicit = str(path_metric.get("selected_strategy") or "")
    metrics = path_metric.get("strategy_metrics")
    if explicit and isinstance(metrics, Mapping) and explicit in metrics:
        return explicit
    if not isinstance(metrics, Mapping) or not metrics:
        return ""
    return max(metrics, key=lambda name: _safe_float(metrics[name].get("train_metric") if isinstance(metrics[name], Mapping) else 0.0))


def estimate_pbo(path_metrics: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    overfit = 0
    for path in path_metrics:
        metrics = path.get("strategy_metrics")
        if not isinstance(metrics, Mapping) or len(metrics) < 2:
            continue
        selected = _selected_strategy(path)
        ranked = sorted(
            (
                (str(name), _safe_float(payload.get("test_metric"), 0.0))
                for name, payload in metrics.items()
                if isinstance(payload, Mapping)
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        if not ranked or selected not in {name for name, _ in ranked}:
            continue
        rank = next(idx + 1 for idx, (name, _) in enumerate(ranked) if name == selected)
        selected_test = next(value for name, value in ranked if name == selected)
        selected_train = _safe_float(metrics[selected].get("train_metric"), 0.0) if isinstance(metrics[selected], Mapping) else 0.0
        is_overfit = rank > len(ranked) / 2.0
        overfit += 1 if is_overfit else 0
        rows.append(
            {
                "path_id": str(path.get("path_id") or ""),
                "selected_strategy": selected,
                "selected_train_metric": selected_train,
                "selected_test_metric": selected_test,
                "selected_test_rank": rank,
                "strategy_count": len(ranked),
                "overfit": bool(is_overfit),
            }
        )
    path_count = len(rows)
    pbo = overfit / path_count if path_count else 0.0
    return sanitize_for_json(
        {
            "method": "cpcv_path_train_selected_holdout_rank",
            "pbo": float(pbo),
            "path_count": path_count,
            "overfit_path_count": int(overfit),
            "pbo_by_path": rows,
            "active_updated": False,
            "customer_prediction_generated": False,
            "message_zh": "CPCV-like PBO 使用多路径 train-selected/test-rank 估计；仅用于 research validation。",
        }
    )


def _bootstrap_p_value(returns: Iterable[Any], *, bootstrap_samples: int, seed: int) -> dict[str, Any]:
    arr = np.asarray([_safe_float(item, 0.0) for item in returns], dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n < 5:
        return {"p_value": 1.0, "observed_mean": float(arr.mean()) if n else 0.0, "sample_count": n, "passed": False}
    observed = float(np.mean(arr))
    centered = arr - observed
    rng = np.random.default_rng(seed)
    boot = np.asarray([float(np.mean(rng.choice(centered, size=n, replace=True))) for _ in range(int(bootstrap_samples))])
    p_value = float(np.mean(boot >= observed))
    return {"p_value": p_value, "observed_mean": observed, "sample_count": n, "passed": bool(p_value <= 0.05 and observed > 0.0)}


def reality_check_by_path(
    path_metrics: Sequence[Mapping[str, Any]],
    *,
    bootstrap_samples: int = 400,
    seed: int = 42,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    aggregate_returns: list[float] = []
    for idx, path in enumerate(path_metrics):
        metrics = path.get("strategy_metrics")
        if not isinstance(metrics, Mapping) or not metrics:
            continue
        selected = _selected_strategy(path)
        selected_metrics = metrics.get(selected)
        if not isinstance(selected_metrics, Mapping):
            continue
        returns = selected_metrics.get("test_returns")
        if not isinstance(returns, list):
            returns = [_safe_float(selected_metrics.get("test_metric"), 0.0)] * max(5, int(selected_metrics.get("test_sample_count") or 5))
        path_payload = _bootstrap_p_value(returns, bootstrap_samples=bootstrap_samples, seed=seed + idx)
        aggregate_returns.extend([_safe_float(item, 0.0) for item in returns])
        rows.append(
            {
                "path_id": str(path.get("path_id") or ""),
                "selected_strategy": selected,
                **path_payload,
            }
        )
    aggregate = _bootstrap_p_value(aggregate_returns, bootstrap_samples=bootstrap_samples, seed=seed + 1000)
    return sanitize_for_json(
        {
            "method": "cpcv_path_bootstrap_reality_check",
            "path_count": len(rows),
            "aggregate_p_value": aggregate["p_value"],
            "aggregate_observed_mean": aggregate["observed_mean"],
            "aggregate_sample_count": aggregate["sample_count"],
            "passed": bool(aggregate["passed"]),
            "reality_check_by_path": rows,
            "active_updated": False,
            "customer_prediction_generated": False,
            "message_zh": "Reality Check 按 CPCV path 做 bootstrap，并汇总 selected strategy 的样本外收益。",
        }
    )


def _normalise_candidate_version(candidate_version: str | None) -> str:
    value = str(candidate_version or "v9").strip().lower()
    return value or "v9"


def _numeric_series(frame: pd.DataFrame, column: str, *, default: float = 0.0) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(float(default), index=frame.index, dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").fillna(float(default))


def _load_oof_frame(candidate_version: str) -> pd.DataFrame:
    base = get_user_output_dir() / "walk_forward" / _normalise_candidate_version(candidate_version)
    frames: list[pd.DataFrame] = []
    for path in sorted(base.glob("oof_trace_*.csv")) if base.exists() else []:
        try:
            frame = pd.read_csv(path)
        except Exception:
            continue
        if frame.empty:
            continue
        if "horizon" not in frame.columns:
            frame["horizon"] = path.stem.replace("oof_trace_", "")
        frames.append(frame)
    if not frames:
        return pd.DataFrame()
    data = pd.concat(frames, ignore_index=True)
    realized = _numeric_series(data, "realized_return", default=0.0)
    direction = _numeric_series(data, "predicted_direction", default=0.0)
    selected = _numeric_series(data, "regime_neutral_selected", default=1.0)
    top10 = _numeric_series(data, "is_high_confidence_top_10", default=0.0)
    top20 = _numeric_series(data, "is_high_confidence_top_20", default=0.0)
    data["y_return"] = realized
    data["model_signal"] = direction
    data["selected_signal_numeric"] = direction.where(selected > 0, 0.0)
    data["top10_signal"] = direction.where(top10 > 0, 0.0)
    data["top20_signal"] = direction.where(top20 > 0, 0.0)
    return data.replace([np.inf, -np.inf], np.nan).dropna(subset=["y_return"]).reset_index(drop=True)


def build_cpcv_report(
    *,
    candidate_version: str = "v9",
    path_metrics: Sequence[Mapping[str, Any]] | None = None,
    sample_count: int | None = None,
    n_groups: int = 6,
    test_group_count: int = 2,
    purge: int = 1,
    embargo: int = 1,
    bootstrap_samples: int = 400,
) -> dict[str, Any]:
    version = _normalise_candidate_version(candidate_version)
    source = "provided_path_metrics"
    splits: list[dict[str, Any]] = []
    if path_metrics is None:
        source = f"walk_forward_oof_{version}"
        frame = _load_oof_frame(version)
        if frame.empty:
            payload = {
                "status": "not_available",
                "candidate_version": version,
                "generated_at": _now(),
                "report_path": str(_report_path()),
                "reason": "missing_oof_trace",
                "research_only": True,
                "active_updated": False,
                "customer_prediction_generated": False,
            }
            _report_path().write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
            return sanitize_for_json(payload)
        splits = build_cpcv_splits(
            sample_count=int(sample_count or len(frame)),
            n_groups=n_groups,
            test_group_count=test_group_count,
            purge=purge,
            embargo=embargo,
        )
        path_metrics = compute_path_metrics(frame, splits, strategy_columns=[col for col in DEFAULT_STRATEGY_COLUMNS if col in frame.columns])
    pbo = estimate_pbo(path_metrics)
    reality = reality_check_by_path(path_metrics, bootstrap_samples=bootstrap_samples)
    payload = {
        "status": "success",
        "generated_at": _now(),
        "candidate_version": version,
        "source": source,
        "report_path": str(_report_path()),
        "split_count": len(path_metrics),
        "cpcv_config": {
            "n_groups": n_groups,
            "test_group_count": test_group_count,
            "purge": purge,
            "embargo": embargo,
            "bootstrap_samples": bootstrap_samples,
            "final_backtest_reverse_tuning_used": False,
        },
        "splits": splits,
        "path_metrics": path_metrics,
        "pbo": pbo,
        "pbo_by_path": pbo.get("pbo_by_path", []),
        "reality_check": reality,
        "reality_check_by_path": reality.get("reality_check_by_path", []),
        "research_only": True,
        "active_updated": False,
        "customer_prediction_generated": False,
        "message_zh": "CPCV-like multi-path validation 已生成；仅用于 research validation，不训练 active、不发布预测。",
    }
    report_path = _report_path()
    report_path.write_text(json.dumps(sanitize_for_json(payload), ensure_ascii=False, indent=2), encoding="utf-8")
    return sanitize_for_json(payload)


def get_cpcv_report(candidate_version: str = "v9") -> dict[str, Any]:
    path = _report_path()
    if path.exists():
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(payload, Mapping):
                return sanitize_for_json(dict(payload))
        except Exception:
            pass
    return build_cpcv_report(candidate_version=candidate_version)
