from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

import numpy as np
import pandas as pd

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .cost_stress_attribution_service import (
    _prepare_oof,
    build_cost_stress_attribution,
    load_candidate_report_for_cost_attribution,
    load_oof_trace_for_cost_attribution,
)


REPORT_FILENAME = "v10_cost_failure_research_report.json"
DEFAULT_FILTERS = (
    "filter_1d_horizon",
    "reduce_high_volatility_exposure",
    "increase_turnover_penalty",
    "limit_signal_flip",
    "minimum_holding_period",
    "stress_2022_filter",
    "cost_aware_thresholding",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _research_dir() -> Path:
    path = _output_dir() / "model_research" / "candidate_v10"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_path() -> Path:
    return _research_dir() / REPORT_FILENAME


def _cpcv_path() -> Path:
    return _research_dir() / "cpcv_validation_v10.json"


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> dict[str, Any]:
    safe = sanitize_for_json(dict(payload))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(safe, ensure_ascii=False, indent=2), encoding="utf-8")
    return safe


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _rows(table: Mapping[str, Any] | None) -> list[dict[str, Any]]:
    if not isinstance(table, Mapping):
        return []
    return [dict(row) for row in table.get("rows", []) if isinstance(row, Mapping)]


def _worst_row(rows: Sequence[Mapping[str, Any]], key: str) -> dict[str, Any]:
    if not rows:
        return {}
    return dict(min(rows, key=lambda row: _safe_float(row.get("net_expectancy_3x"), 0.0)))


def _failure_context(attribution: Mapping[str, Any], candidate_report: Mapping[str, Any]) -> dict[str, Any]:
    horizon_rows = _rows(attribution.get("by_horizon") if isinstance(attribution.get("by_horizon"), Mapping) else {})
    regime_rows = _rows(attribution.get("by_regime") if isinstance(attribution.get("by_regime"), Mapping) else {})
    year_rows = _rows(attribution.get("by_year") if isinstance(attribution.get("by_year"), Mapping) else {})
    worst_horizon = _worst_row(horizon_rows, "horizon")
    worst_regime = _worst_row(regime_rows, "regime_label")
    worst_year = _worst_row(year_rows, "year")
    gate_checks = candidate_report.get("v10_gate_checks") if isinstance(candidate_report.get("v10_gate_checks"), Mapping) else {}
    return {
        "worst_horizon": worst_horizon.get("horizon") or "1d",
        "worst_regime": worst_regime.get("regime_label") or "high_volatility",
        "worst_year": worst_year.get("year") or 2022,
        "failure_drivers": list(attribution.get("failure_drivers") or []),
        "institutional_2x_cost_expectancy": gate_checks.get("two_x_cost_expectancy"),
        "institutional_3x_cost_expectancy": gate_checks.get("three_x_cost_expectancy"),
    }


def build_v10_cost_failure_hypotheses(
    *,
    attribution: Mapping[str, Any] | None = None,
    candidate_report: Mapping[str, Any] | None = None,
) -> list[dict[str, Any]]:
    attribution = attribution or {}
    candidate_report = candidate_report or {}
    context = _failure_context(attribution, candidate_report)
    horizon = str(context["worst_horizon"] or "1d")
    regime = str(context["worst_regime"] or "high_volatility")
    year = str(context["worst_year"] or "2022")
    return [
        {
            "id": "filter_1d_horizon",
            "title": "Filter weak 1d horizon",
            "affected_horizon": "1d",
            "affected_regime": regime,
            "affected_year": year,
            "rationale": "1d horizon is the most cost-sensitive path and should be tested as research-only no-trade.",
            "expected_tradeoff": "Lower turnover and cost drag; lower short-horizon coverage.",
            "risk_of_overfitting": "medium",
        },
        {
            "id": "reduce_high_volatility_exposure",
            "title": "Reduce high volatility exposure",
            "affected_horizon": horizon,
            "affected_regime": "high_volatility",
            "affected_year": year,
            "rationale": "High-volatility contribution can dominate PnL and cost stress.",
            "expected_tradeoff": "Lower regime concentration; may miss high-volatility winners.",
            "risk_of_overfitting": "medium",
        },
        {
            "id": "increase_turnover_penalty",
            "title": "Increase turnover penalty",
            "affected_horizon": horizon,
            "affected_regime": regime,
            "affected_year": year,
            "rationale": "Cost stress failures are sensitive to unnecessary low-edge trades.",
            "expected_tradeoff": "Fewer trades and lower fees; lower market participation.",
            "risk_of_overfitting": "low",
        },
        {
            "id": "limit_signal_flip",
            "title": "Limit signal flip",
            "affected_horizon": horizon,
            "affected_regime": regime,
            "affected_year": year,
            "rationale": "Frequent direction flips convert weak edge into repeated cost drag.",
            "expected_tradeoff": "Lower churn; slower reaction to true reversals.",
            "risk_of_overfitting": "medium",
        },
        {
            "id": "minimum_holding_period",
            "title": "Extend minimum holding period",
            "affected_horizon": "1d",
            "affected_regime": regime,
            "affected_year": year,
            "rationale": "Very short holding windows face the highest relative transaction cost.",
            "expected_tradeoff": "Lower cost drag; may reduce tactical responsiveness.",
            "risk_of_overfitting": "medium",
        },
        {
            "id": "stress_2022_filter",
            "title": "2022-like stress filter",
            "affected_horizon": horizon,
            "affected_regime": "high_volatility",
            "affected_year": "2022",
            "rationale": "Year-specific cost drag suggests a predeclared stress-regime guard should be tested.",
            "expected_tradeoff": "Lower tail-year drag; high overfitting risk if tuned to one year.",
            "risk_of_overfitting": "high",
        },
        {
            "id": "cost_aware_thresholding",
            "title": "Cost-aware thresholding",
            "affected_horizon": horizon,
            "affected_regime": regime,
            "affected_year": year,
            "rationale": "Trades should clear a cost-adjusted edge threshold before selection.",
            "expected_tradeoff": "Better 2x/3x expectancy; fewer selected trades.",
            "risk_of_overfitting": "low",
        },
    ]


def identify_candidate_filters(attribution: Mapping[str, Any] | None = None) -> list[dict[str, Any]]:
    attribution = attribution or {}
    drivers = set(str(item) for item in (attribution.get("failure_drivers") or []))
    filters = [
        {"id": "filter_1d_horizon", "enabled_by": "short_holding_period"},
        {"id": "reduce_high_volatility_exposure", "enabled_by": "regime_specific_cost_drag"},
        {"id": "increase_turnover_penalty", "enabled_by": "high_turnover_horizon"},
        {"id": "limit_signal_flip", "enabled_by": "high_signal_flip_rate"},
        {"id": "minimum_holding_period", "enabled_by": "short_holding_period"},
        {"id": "stress_2022_filter", "enabled_by": "year_specific_cost_drag"},
        {"id": "cost_aware_thresholding", "enabled_by": "institutional_cost_negative"},
    ]
    if not drivers:
        return filters
    return [
        item
        for item in filters
        if item["enabled_by"] in drivers
        or item["enabled_by"] == "institutional_cost_negative"
        and ("institutional_2x_cost_negative" in drivers or "institutional_3x_cost_negative" in drivers)
    ] or filters


def _counterfactual_metrics(work: pd.DataFrame, mask: pd.Series, *, hypothesis_id: str, baseline: Mapping[str, Any]) -> dict[str, Any]:
    selected = work.loc[mask & work["_is_trade"]].copy()
    trade_count = int(len(selected))
    net_2x = float(selected["_net_return_2x"].mean()) if trade_count else 0.0
    net_3x = float(selected["_net_return_3x"].mean()) if trade_count else 0.0
    baseline_trades = _safe_int(baseline.get("trade_count"), 0)
    baseline_net_3x = _safe_float(baseline.get("net_expectancy_3x"), 0.0)
    horizon_values = sorted(str(item) for item in selected.get("horizon", pd.Series(dtype=object)).dropna().unique()) if trade_count else []
    regime_values = sorted(str(item) for item in selected.get("regime_label", pd.Series(dtype=object)).dropna().unique()) if trade_count else []
    year_values = sorted(str(int(item)) for item in selected.get("_year", pd.Series(dtype=object)).dropna().unique()) if trade_count else []
    return sanitize_for_json(
        {
            "hypothesis_id": hypothesis_id,
            "research_only": True,
            "counterfactual_method": "existing_oof_filter_only",
            "trade_count": trade_count,
            "trade_count_delta": trade_count - baseline_trades,
            "trade_retention": trade_count / max(baseline_trades, 1),
            "net_expectancy_2x": net_2x,
            "net_expectancy_3x": net_3x,
            "net_3x_delta": net_3x - baseline_net_3x,
            "affected_horizon": ",".join(horizon_values) if horizon_values else "none",
            "affected_regime": ",".join(regime_values) if regime_values else "none",
            "affected_year": ",".join(year_values) if year_values else "none",
            "expected_tradeoff": "Offline OOF-only estimate; must be predeclared before any future training.",
            "status": "estimated" if trade_count else "no_trades_after_filter",
        }
    )


def _baseline_metrics(work: pd.DataFrame) -> dict[str, Any]:
    trades = work.loc[work["_is_trade"]].copy()
    trade_count = int(len(trades))
    return {
        "trade_count": trade_count,
        "net_expectancy_2x": float(trades["_net_return_2x"].mean()) if trade_count else 0.0,
        "net_expectancy_3x": float(trades["_net_return_3x"].mean()) if trade_count else 0.0,
        "turnover": trade_count / max(len(work), 1),
    }


def estimate_no_train_counterfactuals_from_oof(frame: pd.DataFrame) -> list[dict[str, Any]]:
    if frame.empty:
        return []
    work = _prepare_oof(frame)
    if work.empty or "_is_trade" not in work.columns:
        return []
    baseline = _baseline_metrics(work)
    confidence = pd.to_numeric(work.get("confidence", pd.Series([0.0] * len(work))), errors="coerce").fillna(0.0)
    edge = pd.to_numeric(work.get("trade_edge", pd.Series([0.0] * len(work))), errors="coerce").fillna(0.0)
    cost = pd.to_numeric(work.get("_cost_1x", pd.Series([0.0] * len(work))), errors="coerce").fillna(0.0)
    position = pd.to_numeric(work.get("_position", pd.Series([0.0] * len(work))), errors="coerce").fillna(0.0)
    previous_position = position.shift(1).fillna(position)
    filters: dict[str, pd.Series] = {
        "filter_1d_horizon": work["horizon"].astype(str).str.lower() != "1d",
        "reduce_high_volatility_exposure": (work.get("regime_label", pd.Series([""] * len(work))).astype(str) != "high_volatility") | (confidence >= 0.75),
        "increase_turnover_penalty": edge >= edge.quantile(0.6) if len(edge) else pd.Series([False] * len(work), index=work.index),
        "limit_signal_flip": (position == previous_position) | ~work["_is_trade"],
        "minimum_holding_period": pd.to_numeric(work.get("_holding_period_days", pd.Series([0.0] * len(work))), errors="coerce").fillna(0.0) >= 3.0,
        "stress_2022_filter": work.get("_year", pd.Series([pd.NA] * len(work))).astype("Int64") != 2022,
        "cost_aware_thresholding": edge >= (cost * 3.0),
    }
    return [_counterfactual_metrics(work, mask, hypothesis_id=hypothesis_id, baseline=baseline) for hypothesis_id, mask in filters.items()]


def rank_remediation_hypotheses(
    hypotheses: Sequence[Mapping[str, Any]],
    counterfactuals: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    by_id = {str(item.get("hypothesis_id")): dict(item) for item in counterfactuals if isinstance(item, Mapping)}
    ranked: list[dict[str, Any]] = []
    for hypothesis in hypotheses:
        row = dict(hypothesis)
        cf = by_id.get(str(row.get("id")), {})
        improvement = _safe_float(cf.get("net_3x_delta"), 0.0)
        retention = _safe_float(cf.get("trade_retention"), 0.0)
        risk_penalty = {"low": 0.0, "medium": 0.02, "high": 0.05}.get(str(row.get("risk_of_overfitting")), 0.02)
        row["counterfactual_net_3x_delta"] = improvement
        row["counterfactual_trade_retention"] = retention
        row["rank_score"] = round(improvement + retention * 0.01 - risk_penalty, 6)
        ranked.append(sanitize_for_json(row))
    return sorted(ranked, key=lambda item: _safe_float(item.get("rank_score"), -999.0), reverse=True)


def _missing_report(reason: str, *, candidate_report_path: str = "", oof_paths: list[str] | None = None, write: bool = True) -> dict[str, Any]:
    payload = {
        "status": "skipped",
        "candidate_version": "v10",
        "generated_at": _now(),
        "report_path": str(_report_path()),
        "source_candidate_report_path": candidate_report_path,
        "source_oof_trace_paths": oof_paths or [],
        "hypotheses": [],
        "no_train_counterfactuals": [],
        "ranked_hypotheses": [],
        "expected_tradeoff": "No OOF-only counterfactual was estimated.",
        "affected_horizon": "missing",
        "affected_regime": "missing",
        "affected_year": "missing",
        "risk_of_overfitting": "not_applicable",
        "recommended_next_experiment": "Refresh candidate_v10 cost attribution and OOF evidence before proposing remediation.",
        "manual_approval_recommended": False,
        "research_only": True,
        "blocking_reasons": [reason],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return _write_json(_report_path(), payload) if write else sanitize_for_json(payload)


def build_cost_failure_research_report(*, write: bool = True) -> dict[str, Any]:
    candidate_report, candidate_report_path = load_candidate_report_for_cost_attribution("v10")
    frame, oof_paths = load_oof_trace_for_cost_attribution("v10")
    if not candidate_report:
        return _missing_report("candidate_v10_report_missing", candidate_report_path=candidate_report_path, oof_paths=oof_paths, write=write)
    if frame.empty:
        return _missing_report("oof_trace_missing", candidate_report_path=candidate_report_path, oof_paths=oof_paths, write=write)

    attribution = build_cost_stress_attribution("v10")
    cpcv = _read_json(_cpcv_path())
    hypotheses = build_v10_cost_failure_hypotheses(attribution=attribution, candidate_report=candidate_report)
    counterfactuals = estimate_no_train_counterfactuals_from_oof(frame)
    ranked = rank_remediation_hypotheses(hypotheses, counterfactuals)
    context = _failure_context(attribution, candidate_report)
    best_counterfactual = max(counterfactuals, key=lambda row: _safe_float(row.get("net_3x_delta"), -999.0), default={})
    payload = {
        "status": "ready",
        "candidate_version": "v10",
        "generated_at": _now(),
        "report_path": str(_report_path()),
        "source_candidate_report_path": candidate_report_path,
        "source_oof_trace_paths": oof_paths,
        "source_cost_attribution_path": attribution.get("report_path"),
        "source_cpcv_path": str(_cpcv_path()) if isinstance(cpcv, Mapping) else "",
        "failure_context": context,
        "hypotheses": hypotheses,
        "candidate_filters": identify_candidate_filters(attribution),
        "no_train_counterfactuals": counterfactuals,
        "best_no_train_counterfactual": best_counterfactual,
        "ranked_hypotheses": ranked,
        "expected_tradeoff": "Every estimate is OOF-only and research-only; production changes require a predeclared future experiment.",
        "affected_horizon": context.get("worst_horizon"),
        "affected_regime": context.get("worst_regime"),
        "affected_year": context.get("worst_year"),
        "risk_of_overfitting": ranked[0].get("risk_of_overfitting") if ranked else "medium",
        "recommended_next_experiment": ranked[0].get("id") if ranked else "refresh_oof_evidence",
        "manual_approval_recommended": False,
        "research_only": True,
        "blocking_reasons": [],
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    return _write_json(_report_path(), payload) if write else sanitize_for_json(payload)


def get_v10_cost_failure_research_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return build_cost_failure_research_report(write=False)
