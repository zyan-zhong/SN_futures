from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir


PBO_THRESHOLD = 0.20
REALITY_CHECK_THRESHOLD = 0.05
REGIME_CONCENTRATION_THRESHOLD = 0.70


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _out() -> Path:
    return get_user_output_dir()


def _research_dir() -> Path:
    path = _out() / "model_research" / "candidate_v8"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _json_path() -> Path:
    return _research_dir() / "candidate_v8_validation_diagnostics.json"


def _markdown_path() -> Path:
    return _research_dir() / "candidate_v8_validation_diagnostics.md"


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


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _nested(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def _horizon_to_regime(horizon: str) -> str:
    value = str(horizon)
    if value in {"10d", "20d"}:
        return "high_volatility"
    if value in {"1d", "3d"}:
        return "low_volatility"
    if value == "5d":
        return "range"
    return "unknown"


def _fold_expectancy(fold: Mapping[str, Any]) -> float:
    top20 = _nested(fold, "threshold_optimization", "by_coverage", "top_20pct")
    if isinstance(top20, Mapping):
        return _safe_float(top20.get("expectancy_at_coverage"), _safe_float(fold.get("directional_accuracy"), 0.0))
    metrics = fold.get("metrics") if isinstance(fold.get("metrics"), Mapping) else {}
    return _safe_float(metrics.get("cost_adjusted_expectancy"), _safe_float(fold.get("directional_accuracy"), 0.0))


def _fold_year(fold: Mapping[str, Any]) -> str:
    raw = str(fold.get("validation_start") or fold.get("label_start_time") or "")
    return raw[:4] if len(raw) >= 4 and raw[:4].isdigit() else "unknown"


def _walk_forward_fold_matrix() -> tuple[dict[str, list[dict[str, Any]]], list[str]]:
    base = _out() / "walk_forward" / "v8"
    rows: dict[str, list[dict[str, Any]]] = {}
    for path in sorted(base.glob("wf_*.json")) if base.exists() else []:
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        horizon = str(payload.get("horizon") or path.stem.replace("wf_", ""))
        folds: list[dict[str, Any]] = []
        for idx, fold in enumerate(payload.get("folds") or [], start=1):
            if not isinstance(fold, Mapping):
                continue
            fold_id = str(fold.get("fold") or fold.get("fold_id") or idx)
            folds.append(
                {
                    "fold": fold_id,
                    "year": _fold_year(fold),
                    "horizon": horizon,
                    "regime": _horizon_to_regime(horizon),
                    "expectancy": _fold_expectancy(fold),
                    "validation_samples": _safe_int(fold.get("validation_samples"), 0),
                }
            )
        if folds:
            rows[horizon] = folds
    horizons = sorted(rows, key=lambda item: int(item.replace("d", "")) if item.replace("d", "").isdigit() else 999)
    return rows, horizons


def _summarize_group(rows: Iterable[Mapping[str, Any]], key: str) -> list[dict[str, Any]]:
    grouped: dict[str, dict[str, Any]] = {}
    for row in rows:
        name = str(row.get(key) or "unknown")
        item = grouped.setdefault(name, {"name": name, "overfit_splits": 0, "split_count": 0, "expectancy_sum": 0.0})
        item["split_count"] += 1
        item["overfit_splits"] += 1 if row.get("overfit") else 0
        item["expectancy_sum"] += _safe_float(row.get("selected_holdout_expectancy"), 0.0)
    out: list[dict[str, Any]] = []
    for item in grouped.values():
        split_count = max(_safe_int(item.get("split_count"), 0), 1)
        out.append(
            {
                key: item["name"],
                "overfit_splits": item["overfit_splits"],
                "split_count": item["split_count"],
                "overfit_rate": item["overfit_splits"] / split_count,
                "avg_selected_holdout_expectancy": item["expectancy_sum"] / split_count,
            }
        )
    return sorted(out, key=lambda item: (-_safe_float(item.get("overfit_rate"), 0.0), str(item.get(key))))


def _build_pbo_attribution(validation: Mapping[str, Any]) -> dict[str, Any]:
    folds_by_horizon, horizons = _walk_forward_fold_matrix()
    min_len = min((len(folds) for folds in folds_by_horizon.values()), default=0)
    fold_rows: list[dict[str, Any]] = []
    if len(horizons) >= 2 and min_len >= 1:
        for fold_index in range(min_len):
            train_indexes = [idx for idx in range(min_len) if idx != fold_index]
            train_means: dict[str, float] = {}
            holdout_values: dict[str, float] = {}
            for horizon in horizons:
                values = [_safe_float(row.get("expectancy"), 0.0) for row in folds_by_horizon[horizon][:min_len]]
                train_means[horizon] = float(np.mean([values[idx] for idx in train_indexes])) if train_indexes else values[fold_index]
                holdout_values[horizon] = values[fold_index]
            selected_horizon = max(horizons, key=lambda item: train_means[item])
            sorted_holdout = sorted(holdout_values.items(), key=lambda item: item[1])
            rank = next(idx + 1 for idx, item in enumerate(sorted_holdout) if item[0] == selected_horizon)
            overfit = rank <= len(horizons) / 2
            selected_fold = folds_by_horizon[selected_horizon][fold_index]
            fold_rows.append(
                {
                    "fold": str(selected_fold.get("fold") or fold_index + 1),
                    "year": selected_fold.get("year"),
                    "regime": selected_fold.get("regime"),
                    "selected_horizon": selected_horizon,
                    "selected_train_mean": train_means[selected_horizon],
                    "selected_holdout_expectancy": holdout_values[selected_horizon],
                    "holdout_rank": rank,
                    "strategy_count": len(horizons),
                    "overfit": bool(overfit),
                    "holdout_expectancy_by_horizon": holdout_values,
                }
            )
    pbo_payload = validation.get("probability_of_backtest_overfitting") if isinstance(validation.get("probability_of_backtest_overfitting"), Mapping) else {}
    summary = {
        "pbo": _safe_float(pbo_payload.get("pbo"), 0.0),
        "threshold": PBO_THRESHOLD,
        "gap_to_threshold": max(0.0, _safe_float(pbo_payload.get("pbo"), 0.0) - PBO_THRESHOLD),
        "fold_count": _safe_int(pbo_payload.get("fold_count"), min_len),
        "strategy_count": _safe_int(pbo_payload.get("strategy_count"), len(horizons)),
        "overfit_splits": _safe_int(pbo_payload.get("overfit_splits"), sum(1 for row in fold_rows if row.get("overfit"))),
    }
    return {
        "summary": summary,
        "pbo_attribution_by_fold": fold_rows,
        "pbo_attribution_by_year": _summarize_group(fold_rows, "year"),
        "pbo_attribution_by_regime": _summarize_group(fold_rows, "regime"),
        "pbo_attribution_by_horizon": _summarize_group(fold_rows, "selected_horizon"),
    }


def _build_regime_concentration(stress: Mapping[str, Any], validation: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    regime_stress = stress.get("regime_stress") if isinstance(stress.get("regime_stress"), Mapping) else {}
    raw_rows: list[dict[str, Any]] = []
    total = 0.0
    for regime, payload in regime_stress.items():
        if not isinstance(payload, Mapping):
            continue
        expectancy = _safe_float(payload.get("expectancy"), 0.0)
        contribution_base = abs(expectancy)
        total += contribution_base
        raw_rows.append(
            {
                "regime": str(regime),
                "sample_count": _safe_int(payload.get("sample_count"), 0),
                "fold_count": _safe_int(payload.get("fold_count"), 0),
                "expectancy": expectancy,
                "max_drawdown": _safe_float(payload.get("max_drawdown"), 0.0),
                "_base": contribution_base,
            }
        )
    table: list[dict[str, Any]] = []
    for row in raw_rows:
        contribution = row.pop("_base") / total if total > 1e-12 else 0.0
        row["contribution"] = contribution
        row["threshold"] = REGIME_CONCENTRATION_THRESHOLD
        row["dominant"] = bool(contribution > REGIME_CONCENTRATION_THRESHOLD)
        table.append(row)
    table.sort(key=lambda item: _safe_float(item.get("contribution"), 0.0), reverse=True)
    dominant = table[0] if table else {}
    dominance = validation.get("dominance_checks") if isinstance(validation.get("dominance_checks"), Mapping) else {}
    attribution = {
        "dominant_regime": dominant.get("regime", ""),
        "dominant_contribution": dominant.get("contribution", 0.0),
        "reported_single_regime_contribution": _safe_float(dominance.get("single_regime_contribution"), 0.0),
        "single_regime_dominates": bool(dominance.get("single_regime_dominates", False)),
        "threshold": REGIME_CONCENTRATION_THRESHOLD,
    }
    return table, attribution


def _build_reality_attribution(validation: Mapping[str, Any], regime_attribution: Mapping[str, Any]) -> dict[str, Any]:
    reality = validation.get("reality_check") if isinstance(validation.get("reality_check"), Mapping) else {}
    p_value = _safe_float(reality.get("p_value"), 1.0)
    sample_count = _safe_int(reality.get("sample_count"), 0)
    root_causes: list[str] = []
    if p_value >= REALITY_CHECK_THRESHOLD:
        root_causes.append("near_threshold_not_passed" if p_value - REALITY_CHECK_THRESHOLD <= 0.02 else "not_statistically_significant")
    if sample_count < 100:
        root_causes.append("small_independent_fold_sample")
    if _safe_float(regime_attribution.get("dominant_contribution"), 0.0) > REGIME_CONCENTRATION_THRESHOLD:
        root_causes.append("regime_concentration_reduces_bootstrap_robustness")
    return {
        "passed": bool(reality.get("passed", False)),
        "p_value": p_value,
        "threshold": REALITY_CHECK_THRESHOLD,
        "gap_to_threshold": max(0.0, p_value - REALITY_CHECK_THRESHOLD),
        "observed_mean": _safe_float(reality.get("observed_mean"), 0.0),
        "bootstrap_samples": _safe_int(reality.get("bootstrap_samples"), 0),
        "sample_count": sample_count,
        "root_causes": sorted(set(root_causes)),
    }


def _trade_tables(report: Mapping[str, Any]) -> tuple[dict[str, int], dict[str, float]]:
    application = report.get("stable_policy_application") if isinstance(report.get("stable_policy_application"), Mapping) else {}
    metrics_by_horizon = application.get("metrics_by_horizon") if isinstance(application.get("metrics_by_horizon"), Mapping) else {}
    trade_count = {str(horizon): _safe_int(payload.get("trade_count"), 0) for horizon, payload in metrics_by_horizon.items() if isinstance(payload, Mapping)}
    turnover = {str(horizon): _safe_float(payload.get("turnover"), 0.0) for horizon, payload in metrics_by_horizon.items() if isinstance(payload, Mapping)}
    return dict(sorted(trade_count.items())), dict(sorted(turnover.items()))


def _cost_stress_by_horizon() -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for path in sorted((_out() / "research_backtests" / "v8").glob("metrics_*.json")):
        payload = _read_json(path)
        if not isinstance(payload, Mapping):
            continue
        horizon = str(payload.get("horizon") or path.stem.replace("metrics_", ""))
        stress = payload.get("cost_stress") if isinstance(payload.get("cost_stress"), Mapping) else {}
        out[horizon] = {
            "2x_cost_expectancy": _safe_float(_nested(stress, "2x_cost", "expectancy"), 0.0),
            "3x_cost_expectancy": _safe_float(_nested(stress, "3x_cost", "expectancy"), 0.0),
            "trade_count": _safe_int(payload.get("trade_count"), 0),
            "turnover": _safe_float(payload.get("turnover"), 0.0),
        }
    return out


def _recommended_actions(pbo: Mapping[str, Any], regime: Mapping[str, Any], reality: Mapping[str, Any]) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    if _safe_float(regime.get("dominant_contribution"), 0.0) > REGIME_CONCENTRATION_THRESHOLD:
        actions.append(
            {
                "action": "reduce_single_regime_concentration",
                "priority": "P0",
                "reason": "v8收益仍集中在单一 regime，institutional validation 不允许发布 active。",
                "implementation_hint": "v9 应限制 high-volatility horizon 权重，补足 low-volatility/range 独立样本，或要求跨 regime 同时为正。",
            }
        )
    if _safe_float(pbo.get("summary", {}).get("pbo"), 0.0) > PBO_THRESHOLD:
        actions.append(
            {
                "action": "reduce_pbo_holdout_rank_failures",
                "priority": "P0",
                "reason": "PBO 仍高于门槛，说明训练 fold 选出的 horizon 在留出 fold 排名仍不稳定。",
                "implementation_hint": "v9 阈值选择应按 fold 内完成，并惩罚 holdout rank 落入后半区的 horizon。",
            }
        )
    if _safe_float(reality.get("gap_to_threshold"), 0.0) > 0:
        actions.append(
            {
                "action": "increase_independent_trade_count",
                "priority": "P1",
                "reason": "Reality Check 接近通过但样本仍少，bootstrap 显著性不足。",
                "implementation_hint": "保持低频，但增加跨年份、跨 regime 的独立高置信样本，而不是放宽 gate。",
            }
        )
    actions.append(
        {
            "action": "keep_no_active_until_institutional_pass",
            "priority": "P0",
            "reason": "promotion dry-run pass 不等于 institutional validation pass。",
            "implementation_hint": "继续 dry-run 研究，禁止 active 写入和客户预测。",
        }
    )
    return actions


def _markdown(payload: Mapping[str, Any]) -> str:
    failed = ", ".join(str(item.get("name")) for item in payload.get("failed_checks", []) if isinstance(item, Mapping)) or "none"
    pbo = payload.get("pbo_attribution", {}).get("summary", {}) if isinstance(payload.get("pbo_attribution"), Mapping) else {}
    reality = payload.get("reality_check_bootstrap_summary", {}) if isinstance(payload.get("reality_check_bootstrap_summary"), Mapping) else {}
    dominant = payload.get("regime_concentration_attribution", {}) if isinstance(payload.get("regime_concentration_attribution"), Mapping) else {}
    lines = [
        "# Candidate v8 Validation Diagnostics",
        "",
        "Research-only diagnostics. No active model was published and no customer prediction was generated.",
        "",
        f"- institutional validation: {payload.get('institutional_validation_status')}",
        f"- failed checks: {failed}",
        f"- PBO: {pbo.get('pbo')} (threshold {pbo.get('threshold')})",
        f"- Reality Check p-value: {reality.get('p_value')} (gap {reality.get('gap_to_threshold')})",
        f"- dominant regime: {dominant.get('dominant_regime')} ({dominant.get('dominant_contribution')})",
        "",
        "## Recommended v9 Actions",
    ]
    for item in payload.get("recommended_v9_actions", []):
        if isinstance(item, Mapping):
            lines.append(f"- {item.get('priority')}: {item.get('action')} - {item.get('reason')}")
    return "\n".join(lines) + "\n"


def build_candidate_v8_validation_diagnostics() -> dict[str, Any]:
    validation = _read_json(_out() / "institutional_validation" / "institutional_validation_report_v8.json")
    stress = _read_json(_out() / "institutional_validation" / "stress_tests_v8.json")
    report = _read_json(_out() / "model_research" / "candidate_v8" / "candidate_v8_gated_research_report.json")
    validation = validation if isinstance(validation, Mapping) else {}
    stress = stress if isinstance(stress, Mapping) else {}
    report = report if isinstance(report, Mapping) else {}

    checks = _nested(validation, "promotion_eligibility", "checks")
    failed_checks = [dict(item) for item in checks or [] if isinstance(item, Mapping) and not bool(item.get("passed"))]
    pbo = _build_pbo_attribution(validation)
    regime_table, regime_attribution = _build_regime_concentration(stress, validation)
    reality = _build_reality_attribution(validation, regime_attribution)
    trade_count_by_horizon, turnover_by_horizon = _trade_tables(report)
    payload = {
        "status": "success" if validation else "missing_validation",
        "generated_at": _now(),
        "candidate_version": "v8",
        "institutional_validation_status": validation.get("status", "missing"),
        "validation_passed": bool(validation.get("passed", False)),
        "failed_checks": failed_checks,
        "pbo_attribution": pbo,
        "pbo_attribution_by_fold": pbo["pbo_attribution_by_fold"],
        "pbo_attribution_by_year": pbo["pbo_attribution_by_year"],
        "pbo_attribution_by_regime": pbo["pbo_attribution_by_regime"],
        "reality_check_bootstrap_summary": reality,
        "regime_concentration_table": regime_table,
        "regime_concentration_attribution": regime_attribution,
        "disabled_horizons": list(report.get("disabled_horizons") or []),
        "no_trade_policy_effect": {
            "disabled_horizons": list(report.get("disabled_horizons") or []),
            "no_trade_reasons": list(report.get("no_trade_reasons") or []),
            "v7_vs_v8": report.get("v7_vs_v8") or {},
        },
        "trade_count_by_horizon": trade_count_by_horizon,
        "turnover_by_horizon": turnover_by_horizon,
        "cost_stress_by_horizon": _cost_stress_by_horizon(),
        "recommended_v9_actions": _recommended_actions(pbo, regime_attribution, reality),
        "active_updated": False,
        "customer_prediction_generated": False,
        "json_path": str(_json_path()),
        "markdown_path": str(_markdown_path()),
    }
    _write_json(_json_path(), payload)
    _markdown_path().write_text(_markdown(payload), encoding="utf-8")
    return sanitize_for_json(payload)
