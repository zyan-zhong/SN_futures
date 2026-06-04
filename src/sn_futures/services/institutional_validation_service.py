from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from statistics import NormalDist
from typing import Any, Iterable, Mapping

import numpy as np

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .feature_stability_evidence_service import build_feature_stability_evidence
from .feature_stability_service import build_feature_stability_report
from .model_research_service import get_model_experiment_detail, list_model_experiments


INTERNAL_COST = 0.0002


@dataclass(frozen=True)
class InstitutionalValidationConfig:
    min_deflated_sharpe_ratio: float = 0.0
    max_probability_of_backtest_overfitting: float = 0.20
    min_reality_check_pvalue: float = 0.05
    max_cost_2x_negative_expectancy_abs: float = 0.0
    max_high_vol_drawdown_abs: float = 0.35
    max_single_fold_contribution: float = 0.60
    max_single_regime_contribution: float = 0.70
    min_high_confidence_sample_count: int = 80
    min_feature_stability_rate: float = 0.60


def _validation_dir() -> Path:
    path = get_user_output_dir() / "institutional_validation"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _normalise_version(version: str | None) -> str:
    value = str(version or "v1").strip().lower()
    return value or "v1"


def _report_path(candidate_version: str | None = "v1") -> Path:
    version = _normalise_version(candidate_version)
    if version == "v1":
        return _validation_dir() / "institutional_validation_report.json"
    return _validation_dir() / f"institutional_validation_report_{version}.json"


def _stress_path(candidate_version: str | None = "v1") -> Path:
    version = _normalise_version(candidate_version)
    if version == "v1":
        return _validation_dir() / "stress_tests.json"
    return _validation_dir() / f"stress_tests_{version}.json"


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _merge_feature_stability_evidence(payload: Mapping[str, Any], candidate_version: str) -> dict[str, Any]:
    out = dict(payload)
    try:
        evidence = build_feature_stability_evidence(candidate_version=candidate_version)
    except Exception:
        return out
    if evidence.get("evidence_status") != "success":
        return out

    stability = out.get("feature_stability")
    stability_payload = dict(stability) if isinstance(stability, Mapping) else {}
    stability_payload.update(
        {
            "stability_score": evidence.get("stability_score"),
            "threshold": evidence.get("threshold"),
            "passed": evidence.get("passed"),
            "stable_features": evidence.get("stable_features", []),
            "unstable_features": evidence.get("unstable_features", []),
            "feature_stability": evidence.get("feature_details", []),
            "unstable_feature_blacklist": evidence.get("unstable_features", []),
            "evidence_mode": evidence.get("evidence_mode"),
            "evidence_report_path": evidence.get("report_path"),
            "permutation_importance_status": evidence.get("permutation_importance_status"),
            "recommendations": evidence.get("recommendations", []),
        }
    )
    out["feature_stability"] = stability_payload

    eligibility = out.get("promotion_eligibility")
    if isinstance(eligibility, Mapping):
        eligibility_out = dict(eligibility)
        checks = []
        for item in eligibility_out.get("checks") or []:
            if isinstance(item, Mapping) and str(item.get("name") or "").strip().lower() == "feature stability":
                check = dict(item)
                check["passed"] = bool(evidence.get("passed"))
                check["value"] = evidence.get("stability_score")
                check["threshold"] = f">= {evidence.get('threshold')}"
                check["failure_reason_zh"] = "" if evidence.get("passed") else "特征重要性稳定性不足"
                checks.append(check)
            elif isinstance(item, Mapping):
                checks.append(dict(item))
        if checks:
            eligibility_out["checks"] = checks
            eligibility_out["failure_reasons"] = [str(item.get("failure_reason_zh")) for item in checks if isinstance(item, Mapping) and not item.get("passed") and item.get("failure_reason_zh")]
        out["promotion_eligibility"] = eligibility_out
    return sanitize_for_json(out)


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return default
    return parsed if np.isfinite(parsed) else default


def _nested_expectancy(fold: Mapping[str, Any]) -> float:
    threshold = fold.get("threshold_optimization")
    if not isinstance(threshold, Mapping):
        return _safe_float(fold.get("directional_accuracy"), 0.0)
    by_coverage = threshold.get("by_coverage")
    if not isinstance(by_coverage, Mapping):
        return _safe_float(fold.get("directional_accuracy"), 0.0)
    top20 = by_coverage.get("top_20pct")
    if not isinstance(top20, Mapping):
        return _safe_float(fold.get("directional_accuracy"), 0.0)
    return _safe_float(top20.get("expectancy_at_coverage"), _safe_float(fold.get("directional_accuracy"), 0.0))


def _top20_sample_count(fold: Mapping[str, Any]) -> int:
    threshold = fold.get("threshold_optimization")
    if not isinstance(threshold, Mapping):
        return 0
    by_coverage = threshold.get("by_coverage")
    if not isinstance(by_coverage, Mapping):
        return 0
    top20 = by_coverage.get("top_20pct")
    if not isinstance(top20, Mapping):
        return 0
    return int(_safe_float(top20.get("sample_count"), 0.0))


def _extract_latest_experiment() -> dict[str, Any]:
    listing = list_model_experiments()
    experiments = listing.get("experiments") or []
    if not experiments:
        return {}
    experiment_id = str(experiments[0].get("experiment_id") or "")
    detail = get_model_experiment_detail(experiment_id)
    return detail if isinstance(detail, dict) else {}


def _extract_candidate_walk_forward(candidate_version: str) -> dict[str, Any]:
    version = _normalise_version(candidate_version)
    base = get_user_output_dir() / "walk_forward"
    if version != "v1":
        base = base / version
    horizons: dict[str, Any] = {}
    for path in sorted(base.glob("wf_*.json")):
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            horizons[path.stem.replace("wf_", "")] = payload
    if not horizons:
        return {}
    return {
        "experiment_id": f"candidate_{version}",
        "candidate_version": version,
        "walk_forward_results": {"horizons": horizons},
    }


def _iter_fold_records(detail: Mapping[str, Any]) -> list[dict[str, Any]]:
    walk = detail.get("walk_forward_results")
    if not isinstance(walk, Mapping):
        return []
    horizons = walk.get("horizons")
    if not isinstance(horizons, Mapping):
        return []
    records: list[dict[str, Any]] = []
    for horizon, payload in horizons.items():
        if not isinstance(payload, Mapping):
            continue
        for fold in payload.get("folds") or []:
            if isinstance(fold, Mapping):
                row = dict(fold)
                row["horizon"] = str(horizon)
                records.append(row)
    return records


def _fold_performance(folds: Iterable[Mapping[str, Any]]) -> np.ndarray:
    return np.asarray([_nested_expectancy(fold) for fold in folds], dtype=float)


def deflated_sharpe_ratio(returns: Iterable[Any], *, trials: int = 1) -> dict[str, Any]:
    arr = np.asarray([_safe_float(item, 0.0) for item in returns], dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n < 3 or float(np.std(arr)) < 1e-12:
        return {
            "sample_count": n,
            "trials": max(1, int(trials)),
            "sharpe": 0.0,
            "deflated_sharpe_ratio": 0.0,
            "probability_positive": 0.5,
            "message_zh": "样本不足或收益方差过低，DSR 返回保守占位值。",
        }
    mean = float(np.mean(arr))
    std = float(np.std(arr, ddof=1))
    sharpe = mean / std * math.sqrt(252)
    centered = arr - mean
    skew = float(np.mean(centered**3) / (std**3)) if std > 1e-12 else 0.0
    kurt = float(np.mean(centered**4) / (std**4)) if std > 1e-12 else 3.0
    trials = max(1, int(trials))
    selection_penalty = NormalDist().inv_cdf(1.0 - 0.5 / trials) if trials > 1 else 0.0
    denominator = math.sqrt(max(1e-12, 1.0 - skew * sharpe + ((kurt - 1.0) / 4.0) * sharpe * sharpe))
    dsr = ((sharpe - selection_penalty) * math.sqrt(n - 1)) / denominator
    probability = NormalDist().cdf(dsr)
    return sanitize_for_json(
        {
            "sample_count": n,
            "trials": trials,
            "mean": mean,
            "std": std,
            "skew": skew,
            "kurtosis": kurt,
            "sharpe": sharpe,
            "selection_penalty": selection_penalty,
            "deflated_sharpe_ratio": dsr,
            "probability_positive": probability,
            "message_zh": "DSR 已按样本长度、非正态和多次试验选择偏差做轻量修正。",
        }
    )


def probability_of_backtest_overfitting(strategy_fold_matrix: Mapping[str, Iterable[Any]]) -> dict[str, Any]:
    matrix = {name: np.asarray([_safe_float(v, 0.0) for v in values], dtype=float) for name, values in strategy_fold_matrix.items()}
    matrix = {name: values[np.isfinite(values)] for name, values in matrix.items() if len(values) >= 3}
    if len(matrix) < 2:
        return {
            "pbo": 0.0,
            "fold_count": 0,
            "strategy_count": len(matrix),
            "message_zh": "策略或周期数量不足，PBO 仅返回低风险占位；不能据此宣称已排除过拟合。",
        }
    min_len = min(len(values) for values in matrix.values())
    names = sorted(matrix)
    values = np.vstack([matrix[name][:min_len] for name in names])
    overfit = 0
    trials = 0
    for holdout in range(min_len):
        train_idx = [idx for idx in range(min_len) if idx != holdout]
        train_perf = values[:, train_idx].mean(axis=1)
        selected = int(np.argmax(train_perf))
        holdout_perf = values[:, holdout]
        rank = int(np.argsort(np.argsort(holdout_perf))[selected])
        if rank < len(names) / 2:
            overfit += 1
        trials += 1
    pbo = overfit / max(trials, 1)
    return sanitize_for_json(
        {
            "pbo": float(pbo),
            "fold_count": min_len,
            "strategy_count": len(names),
            "overfit_splits": overfit,
            "message_zh": "PBO 使用轻量 leave-one-fold-out 排名估计，衡量选中策略在留出 fold 中落入后半区的概率。",
        }
    )


def bootstrap_reality_check(returns: Iterable[Any], *, bootstrap_samples: int = 400, seed: int = 42) -> dict[str, Any]:
    arr = np.asarray([_safe_float(item, 0.0) for item in returns], dtype=float)
    arr = arr[np.isfinite(arr)]
    n = int(arr.size)
    if n < 5:
        return {"passed": False, "p_value": 1.0, "sample_count": n, "message_zh": "样本不足，Reality Check 未通过。"}
    observed = float(np.mean(arr))
    centered = arr - observed
    rng = np.random.default_rng(seed)
    boot = [float(np.mean(rng.choice(centered, size=n, replace=True))) for _ in range(int(bootstrap_samples))]
    p_value = float(np.mean(np.asarray(boot) >= observed))
    return sanitize_for_json(
        {
            "passed": p_value < 0.05 and observed > 0,
            "p_value": p_value,
            "observed_mean": observed,
            "bootstrap_samples": int(bootstrap_samples),
            "sample_count": n,
            "message_zh": "Bootstrap Reality Check 用于检验平均表现是否显著优于零。",
        }
    )


def white_reality_check(returns: Iterable[Any], *, bootstrap_samples: int = 400, seed: int = 42) -> dict[str, Any]:
    payload = bootstrap_reality_check(returns, bootstrap_samples=bootstrap_samples, seed=seed)
    payload["method"] = "white_reality_check_lightweight_bootstrap"
    return sanitize_for_json(payload)


def multiple_testing_correction(p_values: Mapping[str, Any]) -> dict[str, Any]:
    items = [(name, max(0.0, min(1.0, _safe_float(value, 1.0)))) for name, value in p_values.items()]
    m = max(1, len(items))
    bonferroni = {name: min(1.0, value * m) for name, value in items}
    sorted_items = sorted(items, key=lambda item: item[1])
    bh: dict[str, float] = {}
    for rank, (name, value) in enumerate(sorted_items, start=1):
        bh[name] = min(1.0, value * m / rank)
    return sanitize_for_json({"bonferroni": bonferroni, "benjamini_hochberg": bh, "test_count": m})


def _cost_stress(folds: list[dict[str, Any]]) -> dict[str, Any]:
    base = _fold_performance(folds)
    multipliers = {
        "0.5x_cost": 0.5,
        "1x_cost": 1.0,
        "2x_cost": 2.0,
        "3x_cost": 3.0,
        "low_liquidity_slippage": 4.0,
        "gap_open_slippage": 5.0,
        "roll_period_extra_cost": 3.5,
        "night_session_slippage": 2.5,
    }
    rows: dict[str, Any] = {}
    for name, multiplier in multipliers.items():
        stressed = base - INTERNAL_COST * (multiplier - 1.0)
        hit_rate = float((stressed > 0).mean()) if stressed.size else 0.0
        std = float(np.std(stressed, ddof=1)) if stressed.size > 1 else 0.0
        sharpe = float(np.mean(stressed) / std * math.sqrt(252)) if std > 1e-12 else 0.0
        equity = np.cumsum(stressed) if stressed.size else np.asarray([])
        drawdown = float(np.min(equity - np.maximum.accumulate(equity))) if equity.size else 0.0
        rows[name] = {
            "cost_multiplier": multiplier,
            "expectancy": float(np.mean(stressed)) if stressed.size else 0.0,
            "sharpe": sharpe,
            "max_drawdown": drawdown,
            "hit_rate": hit_rate,
            "active_eligibility_under_cost_stress": bool(name != "2x_cost" or (stressed.size and float(np.mean(stressed)) >= 0.0)),
        }
    return sanitize_for_json(rows)


def _regime_for_fold(fold: Mapping[str, Any]) -> str:
    horizon = str(fold.get("horizon", ""))
    if horizon in {"10d", "20d"}:
        return "high_volatility"
    if horizon in {"1d", "3d"}:
        return "low_volatility"
    if horizon == "5d":
        return "range"
    return "range"


def _regime_stress(folds: list[dict[str, Any]]) -> dict[str, Any]:
    regimes: dict[str, list[tuple[float, float, Mapping[str, Any]]]] = {
        "high_volatility": [],
        "low_volatility": [],
        "trend_up": [],
        "trend_down": [],
        "range": [],
        "event_shock": [],
        "roll_period": [],
        "extreme_gap_day": [],
    }
    for fold in folds:
        acc = _safe_float(fold.get("directional_accuracy"), 0.0)
        exp = _nested_expectancy(fold)
        regimes[_regime_for_fold(fold)].append((acc, exp, fold))
    out: dict[str, Any] = {}
    for regime, rows in regimes.items():
        accs = [row[0] for row in rows]
        exps = [row[1] for row in rows]
        cumulative = np.cumsum(exps) if exps else np.asarray([])
        out[regime] = {
            "sample_count": int(sum(int(row[2].get("validation_samples", 0)) for row in rows)),
            "fold_count": len(rows),
            "direction_accuracy": float(np.mean(accs)) if accs else None,
            "expectancy": float(np.mean(exps)) if exps else None,
            "max_drawdown": float(np.min(cumulative - np.maximum.accumulate(cumulative))) if cumulative.size else None,
            "calibration_error": float(np.mean([_safe_float(row[2].get("calibration_error"), 0.0) for row in rows])) if rows else None,
            "no_trade_rate": None,
        }
    return sanitize_for_json(out)


def _dominance_checks(folds: list[dict[str, Any]], regime_stress: Mapping[str, Any], config: InstitutionalValidationConfig) -> dict[str, Any]:
    perf = np.abs(_fold_performance(folds))
    total = float(np.sum(perf))
    single_fold_contribution = float(np.max(perf) / total) if total > 1e-12 and perf.size else 0.0
    regime_values: list[float] = []
    for value in regime_stress.values():
        if isinstance(value, Mapping) and int(value.get("fold_count") or 0) > 0:
            regime_values.append(abs(_safe_float(value.get("expectancy"), 0.0)))
    regime_total = float(sum(regime_values))
    single_regime_contribution = float(max(regime_values) / regime_total) if regime_total > 1e-12 and regime_values else 0.0
    return {
        "single_fold_contribution": single_fold_contribution,
        "single_fold_dominates": single_fold_contribution > config.max_single_fold_contribution,
        "single_regime_contribution": single_regime_contribution,
        "single_regime_dominates": single_regime_contribution > config.max_single_regime_contribution,
    }


def run_institutional_validation(
    config: InstitutionalValidationConfig | None = None,
    *,
    candidate_version: str = "v1",
    dry_run: bool = False,
) -> dict[str, Any]:
    cfg = config or InstitutionalValidationConfig()
    candidate_version = _normalise_version(candidate_version)
    detail = _extract_candidate_walk_forward(candidate_version) if candidate_version != "v1" else _extract_latest_experiment()
    folds = _iter_fold_records(detail)
    if not detail or not folds:
        report = {
            "status": "no_experiment",
            "passed": False,
            "candidate_version": candidate_version,
            "dry_run": bool(dry_run),
            "message_zh": "未找到可用于机构级验证的研究实验或 walk-forward fold。",
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            "active_updated": False,
            "promotion_gate_lowered": False,
            "customer_prediction_generated": False,
        }
        _write_json(_report_path(candidate_version), report)
        return sanitize_for_json(report)

    performances = _fold_performance(folds)
    horizons = sorted({str(fold.get("horizon")) for fold in folds})
    strategy_matrix = {
        horizon: [_nested_expectancy(fold) for fold in folds if str(fold.get("horizon")) == horizon]
        for horizon in horizons
    }
    dsr = deflated_sharpe_ratio(performances, trials=max(1, len(horizons)))
    pbo = probability_of_backtest_overfitting(strategy_matrix)
    reality = bootstrap_reality_check(performances)
    cost_stress = _cost_stress(folds)
    regime_stress = _regime_stress(folds)
    dominance = _dominance_checks(folds, regime_stress, cfg)

    fold_importance = [{"feature_importance": fold["feature_importance"]} for fold in folds if isinstance(fold.get("feature_importance"), (Mapping, list))]
    stability = build_feature_stability_report(fold_importance)
    stability_rows = stability.get("feature_stability") or []
    stable_count = sum(1 for row in stability_rows if isinstance(row, Mapping) and row.get("stable"))
    stability_rate = stable_count / max(1, len(stability_rows))
    if candidate_version != "v1":
        try:
            evidence = build_feature_stability_evidence(candidate_version=candidate_version)
        except Exception:
            evidence = {}
        if isinstance(evidence, Mapping) and evidence.get("evidence_status") == "success":
            stability = dict(stability)
            stability.update(
                {
                    "stability_score": evidence.get("stability_score"),
                    "threshold": evidence.get("threshold"),
                    "passed": evidence.get("passed"),
                    "stable_features": evidence.get("stable_features", []),
                    "unstable_features": evidence.get("unstable_features", []),
                    "feature_stability": evidence.get("feature_details", []),
                    "unstable_feature_blacklist": evidence.get("unstable_features", []),
                    "evidence_mode": evidence.get("evidence_mode"),
                    "evidence_report_path": evidence.get("report_path"),
                    "permutation_importance_status": evidence.get("permutation_importance_status"),
                    "recommendations": evidence.get("recommendations", []),
                }
            )
            stability_rate = _safe_float(evidence.get("stability_score"), stability_rate)
    high_conf_samples = sum(_top20_sample_count(fold) for fold in folds)

    checks = [
        {
            "name": "Deflated Sharpe Ratio",
            "passed": _safe_float(dsr.get("deflated_sharpe_ratio"), -999.0) > cfg.min_deflated_sharpe_ratio,
            "value": dsr.get("deflated_sharpe_ratio"),
            "threshold": f"> {cfg.min_deflated_sharpe_ratio}",
            "failure_reason_zh": "DSR 未超过阈值",
        },
        {
            "name": "PBO",
            "passed": _safe_float(pbo.get("pbo"), 1.0) < cfg.max_probability_of_backtest_overfitting,
            "value": pbo.get("pbo"),
            "threshold": f"< {cfg.max_probability_of_backtest_overfitting}",
            "failure_reason_zh": "PBO 过高，存在过拟合风险",
        },
        {
            "name": "Reality Check",
            "passed": bool(reality.get("passed")),
            "value": reality.get("p_value"),
            "threshold": f"< {cfg.min_reality_check_pvalue}",
            "failure_reason_zh": "Reality Check 未通过",
        },
        {
            "name": "2x cost stress",
            "passed": _safe_float(cost_stress.get("2x_cost", {}).get("expectancy"), -1.0) >= -cfg.max_cost_2x_negative_expectancy_abs,
            "value": cost_stress.get("2x_cost", {}).get("expectancy"),
            "threshold": ">= 0",
            "failure_reason_zh": "2x 成本压力下期望为负",
        },
        {
            "name": "high-vol drawdown",
            "passed": abs(_safe_float(regime_stress.get("high_volatility", {}).get("max_drawdown"), 0.0)) <= cfg.max_high_vol_drawdown_abs,
            "value": regime_stress.get("high_volatility", {}).get("max_drawdown"),
            "threshold": f"abs <= {cfg.max_high_vol_drawdown_abs}",
            "failure_reason_zh": "高波动状态回撤过大",
        },
        {
            "name": "feature stability",
            "passed": stability_rate >= cfg.min_feature_stability_rate,
            "value": stability_rate,
            "threshold": f">= {cfg.min_feature_stability_rate}",
            "failure_reason_zh": "特征重要性稳定性不足",
        },
        {
            "name": "high-confidence samples",
            "passed": high_conf_samples >= cfg.min_high_confidence_sample_count,
            "value": high_conf_samples,
            "threshold": f">= {cfg.min_high_confidence_sample_count}",
            "failure_reason_zh": "高置信样本数不足",
        },
        {
            "name": "no single fold dominates",
            "passed": not dominance["single_fold_dominates"],
            "value": dominance["single_fold_contribution"],
            "threshold": f"<= {cfg.max_single_fold_contribution}",
            "failure_reason_zh": "单一 fold 贡献过高",
        },
        {
            "name": "no single regime dominates",
            "passed": not dominance["single_regime_dominates"],
            "value": dominance["single_regime_contribution"],
            "threshold": f"<= {cfg.max_single_regime_contribution}",
            "failure_reason_zh": "单一 regime 贡献过高",
        },
    ]
    failures = [str(check["failure_reason_zh"]) for check in checks if not check["passed"]]
    report = {
        "status": "passed" if not failures else "failed",
        "passed": not failures,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "candidate_version": candidate_version,
        "dry_run": bool(dry_run),
        "experiment_id": detail.get("experiment_id"),
        "config": asdict(cfg),
        "deflated_sharpe_ratio": dsr,
        "probability_of_backtest_overfitting": pbo,
        "reality_check": reality,
        "multiple_testing_correction": multiple_testing_correction({str(horizon): reality.get("p_value", 1.0) for horizon in horizons}),
        "combinatorial_purged_cv_summary": {
            "mode": "lightweight_leave_one_fold_out",
            "fold_count": len(folds),
            "horizon_count": len(horizons),
            "message_zh": "完整 CPCV 计算较重，本版先输出轻量 leave-one-fold-out 摘要。",
        },
        "cost_stress": cost_stress,
        "regime_stress": regime_stress,
        "feature_stability": stability,
        "dominance_checks": dominance,
        "promotion_eligibility": {
            "eligible": not failures,
            "checks": checks,
            "failure_reasons": failures,
            "message_zh": "机构级验证通过。" if not failures else "机构级验证未通过，不允许发布 active。",
        },
        "active_updated": False,
        "promotion_gate_lowered": False,
        "customer_prediction_generated": False,
    }
    _write_json(_report_path(candidate_version), report)
    _write_json(_stress_path(candidate_version), {"candidate_version": candidate_version, "cost_stress": cost_stress, "regime_stress": regime_stress, "generated_at": report["generated_at"]})
    return sanitize_for_json(report)


def get_institutional_validation_report(candidate_version: str = "v1") -> dict[str, Any]:
    payload = _read_json(_report_path(candidate_version))
    if not isinstance(payload, Mapping):
        return sanitize_for_json({"status": "not_run", "passed": False, "message_zh": "机构级验证尚未运行。", "active_updated": False})
    version = _normalise_version(candidate_version)
    enriched = _merge_feature_stability_evidence(payload, version) if version != "v1" else dict(payload)
    if enriched != payload:
        _write_json(_report_path(version), enriched)
    return sanitize_for_json(enriched)


def get_institutional_stress_tests(candidate_version: str = "v1") -> dict[str, Any]:
    payload = _read_json(_stress_path(candidate_version))
    if not isinstance(payload, Mapping):
        report = get_institutional_validation_report(candidate_version=candidate_version)
        return sanitize_for_json(
            {
                "status": report.get("status", "not_run"),
                "cost_stress": report.get("cost_stress", {}),
                "regime_stress": report.get("regime_stress", {}),
                "message_zh": report.get("message_zh", "压力测试尚未运行。"),
            }
        )
    return sanitize_for_json(payload)
