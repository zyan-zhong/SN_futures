from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


V9_STABLE_MODELS = (
    "hist_gradient_boosting",
    "random_forest",
    "huber_return",
    "elasticnet_return",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _out() -> Path:
    return get_user_output_dir()


def _research_dir(candidate_version: str = "v9") -> Path:
    path = _out() / "model_research" / f"candidate_{candidate_version}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _policy_path(candidate_version: str = "v9") -> Path:
    return _research_dir(candidate_version) / f"regime_neutral_strategy_policy_{candidate_version}.json"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _nested(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _horizon_days(horizon: str) -> int:
    try:
        return max(1, int(str(horizon).lower().replace("d", "")))
    except Exception:
        return 1


def horizon_to_regime(horizon: str) -> str:
    value = str(horizon)
    if value in {"10d", "20d"}:
        return "high_volatility"
    if value in {"1d", "3d"}:
        return "low_volatility"
    if value == "5d":
        return "range"
    return "unknown"


def _v8_models(v8_report: Mapping[str, Any]) -> list[str]:
    models = _nested(v8_report, "stable_strategy_policy", "complexity", "models")
    if isinstance(models, list):
        values = [str(item) for item in models if str(item)]
    else:
        values = list(V9_STABLE_MODELS)
    selected = [item for item in V9_STABLE_MODELS if item in set(values)]
    return selected or ["hist_gradient_boosting", "random_forest"]


def build_regime_neutral_strategy_policy(
    *,
    v8_diagnostics: Mapping[str, Any] | None = None,
    v8_report: Mapping[str, Any] | None = None,
    target_candidate_version: str = "v9",
    write: bool = False,
) -> dict[str, Any]:
    diagnostics = v8_diagnostics or {}
    report = v8_report or {}
    pbo = _safe_float(_nested(diagnostics, "pbo_attribution", "summary", "pbo"), 1.0)
    pbo_threshold = _safe_float(_nested(diagnostics, "pbo_attribution", "summary", "threshold"), 0.20)
    reality = _safe_float(_nested(diagnostics, "reality_check_bootstrap_summary", "p_value"), 1.0)
    dominant_regime = str(_nested(diagnostics, "regime_concentration_attribution", "dominant_regime") or "")
    dominant_contribution = _safe_float(
        _nested(diagnostics, "regime_concentration_attribution", "dominant_contribution"),
        0.0,
    )
    capped_regimes = [dominant_regime] if dominant_regime and dominant_contribution > 0.70 else []
    models = _v8_models(report)
    payload = {
        "status": "success",
        "generated_at": _now(),
        "candidate_version": str(target_candidate_version),
        "base_candidate": "v8",
        "dataset_version": "v7",
        "feature_store_version": "v7",
        "feature_set": "tushare_cost_positioning_regime_neutral",
        "policy_path": str(_policy_path(str(target_candidate_version))),
        "regime_trade_quota": {
            "max_single_regime_trade_share": 0.55,
            "max_single_regime_expectancy_share": 0.65,
            "min_selected_regime_count": 2,
            "capped_regimes": capped_regimes,
            "confidence_boost_for_capped_regime": 0.05,
            "confidence_discount_for_underrepresented_regime": 0.04,
        },
        "fold_trade_quota": {
            "max_single_fold_trade_share": 0.35,
            "min_folds_with_trades": 3,
            "reject_if_single_fold_exceeds": True,
        },
        "year_trade_quota": {
            "max_single_year_trade_share": 0.35,
            "min_years_with_trades": 3,
        },
        "threshold_policy": {
            "global_max_trade_rate": 0.035,
            "min_selected_trades": 80,
            "min_confidence": 0.58,
            "min_trade_edge": 0.0,
            "high_volatility_min_confidence": 0.72 if "high_volatility" in capped_regimes else 0.66,
            "low_volatility_min_confidence": 0.54,
            "range_min_confidence": 0.54,
            "horizon_overrides": {
                "1d": {"trade_enabled": False, "reason": "weak_v8_horizon"},
                "3d": {"trade_enabled": True, "max_trade_rate": 0.018},
                "5d": {"trade_enabled": True, "max_trade_rate": 0.018},
                "10d": {"trade_enabled": True, "max_trade_rate": 0.012},
                "20d": {"trade_enabled": True, "max_trade_rate": 0.012},
            },
        },
        "cpcv_like_pbo_validation": {
            "mode": "leave_one_fold_out_rank_with_regime_quota",
            "current_pbo": pbo,
            "target_pbo": pbo_threshold,
            "requires_pbo_below_target": True,
        },
        "objective": {
            "maximize": ["DSR", "cost_adjusted_expectancy", "regime_balance", "independent_trade_count"],
            "minimize": ["PBO", "single_regime_concentration", "single_year_concentration", "single_fold_concentration"],
            "reality_check_gap": max(0.0, reality - 0.05),
        },
        "complexity": {
            "models": models,
            "not_higher_than_v8": True,
            "selection_only": True,
            "new_model_families_added": [],
        },
        "training_fold_only_selection": True,
        "validation_fold_tuning": False,
        "uses_final_backtest_for_tuning": False,
        "active_updated": False,
        "customer_prediction_generated": False,
        "promotion_gate_lowered": False,
        "message": "Regime-neutral candidate_v9 policy built from v8 failure attribution without increasing model complexity.",
    }
    if write:
        _write_json(_policy_path(str(target_candidate_version)), payload)
    return sanitize_for_json(payload)


def _date_year(frame: pd.DataFrame) -> pd.Series:
    for col in ("label_start_time", "timestamp"):
        if col in frame.columns:
            return pd.to_datetime(frame[col], errors="coerce").dt.year.fillna(0).astype(int).astype(str)
    return pd.Series(["unknown"] * len(frame), index=frame.index)


def _selection_score(frame: pd.DataFrame) -> pd.Series:
    confidence = pd.to_numeric(frame.get("confidence", 0.0), errors="coerce").fillna(0.0).astype(float)
    edge = pd.to_numeric(frame.get("trade_edge", 0.0), errors="coerce").fillna(0.0).astype(float)
    return confidence.abs() * (edge.abs() + 1e-9)


def select_regime_neutral_trades(frame: pd.DataFrame, policy: Mapping[str, Any]) -> pd.Series:
    if frame.empty:
        return pd.Series(False, index=frame.index)
    work = frame.copy()
    if "regime_label" not in work.columns:
        work["regime_label"] = work.get("__horizon", "").map(horizon_to_regime) if "__horizon" in work.columns else "unknown"
    if "fold_id" not in work.columns:
        work["fold_id"] = "unknown"
    work["__year"] = _date_year(work)
    predicted = pd.to_numeric(work.get("predicted_direction", 0), errors="coerce").fillna(0).astype(int)
    confidence = pd.to_numeric(work.get("confidence", 0.0), errors="coerce").fillna(0.0).astype(float)
    edge = pd.to_numeric(work.get("trade_edge", 0.0), errors="coerce").fillna(0.0).astype(float)
    thresholds = policy.get("threshold_policy") if isinstance(policy.get("threshold_policy"), Mapping) else {}
    global_cap = max(1, int(np.floor(len(work) * _safe_float(thresholds.get("global_max_trade_rate"), 0.035))))
    min_edge = _safe_float(thresholds.get("min_trade_edge"), 0.0)

    min_conf_by_regime = {
        "high_volatility": _safe_float(thresholds.get("high_volatility_min_confidence"), 0.66),
        "low_volatility": _safe_float(thresholds.get("low_volatility_min_confidence"), 0.54),
        "range": _safe_float(thresholds.get("range_min_confidence"), 0.54),
        "unknown": _safe_float(thresholds.get("min_confidence"), 0.58),
    }
    candidates = predicted.ne(0) & edge.ge(min_edge)
    horizon_overrides = thresholds.get("horizon_overrides") if isinstance(thresholds.get("horizon_overrides"), Mapping) else {}
    if "__horizon" in work.columns and isinstance(horizon_overrides, Mapping):
        for horizon, override in horizon_overrides.items():
            if isinstance(override, Mapping) and not bool(override.get("trade_enabled", True)):
                candidates &= ~work["__horizon"].astype(str).eq(str(horizon))
    for regime, min_confidence in min_conf_by_regime.items():
        mask = work["regime_label"].astype(str).eq(regime)
        candidates &= ~mask | confidence.ge(min_confidence)

    regime_quota = policy.get("regime_trade_quota") if isinstance(policy.get("regime_trade_quota"), Mapping) else {}
    fold_quota = policy.get("fold_trade_quota") if isinstance(policy.get("fold_trade_quota"), Mapping) else {}
    year_quota = policy.get("year_trade_quota") if isinstance(policy.get("year_trade_quota"), Mapping) else {}
    min_global = max(
        1,
        int(_safe_float(regime_quota.get("min_selected_regime_count"), 2)),
        int(_safe_float(fold_quota.get("min_folds_with_trades"), 3)),
        int(_safe_float(year_quota.get("min_years_with_trades"), 3)),
    )
    global_cap = max(global_cap, min_global)
    max_regime = max(1, int(np.floor(global_cap * _safe_float(regime_quota.get("max_single_regime_trade_share"), 0.55))))
    max_fold = max(1, int(np.floor(global_cap * _safe_float(fold_quota.get("max_single_fold_trade_share"), 0.35))))
    max_year = max(1, int(np.floor(global_cap * _safe_float(year_quota.get("max_single_year_trade_share"), 0.35))))

    selected = pd.Series(False, index=work.index)
    regime_counts: dict[str, int] = {}
    fold_counts: dict[str, int] = {}
    year_counts: dict[str, int] = {}
    scores = _selection_score(work).where(candidates, -np.inf)
    for idx in scores.sort_values(ascending=False).index:
        if not np.isfinite(float(scores.loc[idx])):
            continue
        regime = str(work.at[idx, "regime_label"])
        fold = str(work.at[idx, "fold_id"])
        year = str(work.at[idx, "__year"])
        if regime_counts.get(regime, 0) >= max_regime:
            continue
        if fold_counts.get(fold, 0) >= max_fold:
            continue
        if year_counts.get(year, 0) >= max_year:
            continue
        selected.loc[idx] = True
        regime_counts[regime] = regime_counts.get(regime, 0) + 1
        fold_counts[fold] = fold_counts.get(fold, 0) + 1
        year_counts[year] = year_counts.get(year, 0) + 1
        if int(selected.sum()) >= global_cap:
            break
    min_total = int(_safe_float(thresholds.get("min_selected_trades"), 80)) if len(work) >= 1000 else 1
    selected = _enforce_realized_share(selected, work["regime_label"].astype(str), scores, _safe_float(regime_quota.get("max_single_regime_trade_share"), 0.55), min_total=min_total)
    selected = _enforce_realized_share(selected, work["fold_id"].astype(str), scores, _safe_float(fold_quota.get("max_single_fold_trade_share"), 0.35), min_total=min_total)
    selected = _enforce_realized_share(selected, work["__year"].astype(str), scores, _safe_float(year_quota.get("max_single_year_trade_share"), 0.35), min_total=min_total)
    return selected.astype(bool)


def _enforce_realized_share(selected: pd.Series, groups: pd.Series, scores: pd.Series, max_share: float, *, min_total: int = 1) -> pd.Series:
    out = selected.astype(bool).copy()
    max_share = max(0.01, min(1.0, float(max_share)))
    min_total = max(1, int(min_total))
    while int(out.sum()) > min_total:
        selected_groups = groups.loc[out]
        counts = selected_groups.value_counts()
        if counts.empty:
            break
        dominant_group = str(counts.index[0])
        dominant_count = int(counts.iloc[0])
        total = int(out.sum())
        if dominant_count / max(total, 1) <= max_share:
            break
        candidates = out & groups.astype(str).eq(dominant_group)
        candidate_scores = scores.where(candidates, np.inf)
        drop_index = candidate_scores.idxmin()
        if not np.isfinite(float(candidate_scores.loc[drop_index])):
            break
        out.loc[drop_index] = False
    return out.astype(bool)
