from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from ..utils.secret_sanitizer import sanitize_mapping, sanitize_text
from .feature_stability_evidence_service import build_feature_stability_evidence
from .provider_status_canonical_service import build_canonical_provider_status


MISSING_FUNDAMENTAL_GROUPS = ("basis", "inventory", "lme_tin", "cross_market", "event", "term_structure")
DATA_SOURCE_STATUS_FILES = (
    ("tushare_provider_status", ("fundamentals", "tushare_provider_status.json")),
    ("managed_proxy_status", ("fundamentals", "managed_proxy_status.json")),
    ("fx_macro_provider_status", ("fundamentals", "fx_macro_provider_status.json")),
    ("news_provider_status", ("events", "news_provider_status.json")),
    ("shfe_public_provider_status", ("fundamentals", "shfe_public_provider_status.json")),
    ("lme_tin_provider_status", ("fundamentals", "lme_tin_provider_status.json")),
)
DEFAULT_THRESHOLDS = {
    "pbo": 0.2,
    "dsr": 0.0,
    "worst_fold_accuracy": 0.52,
    "worst_year_accuracy": 0.52,
    "worst_regime_accuracy": 0.52,
    "cost_stress_2x_expectancy": 0.0,
    "cost_stress_3x_expectancy": 0.0,
    "max_drawdown": 0.2,
    "feature_stability_score": 0.55,
    "high_confidence_sample_count": 100,
}


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _out() -> Path:
    return get_user_output_dir()


def _read_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(sanitize_for_json(sanitize_mapping(dict(payload))), ensure_ascii=False, indent=2), encoding="utf-8")


def _walk_values(payload: Any) -> Iterable[tuple[str, Any]]:
    if isinstance(payload, Mapping):
        for key, value in payload.items():
            yield str(key), value
            yield from _walk_values(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from _walk_values(item)


def _first_scalar(payload: Any, key_names: Iterable[str]) -> Any:
    wanted = {key.lower() for key in key_names}
    for key, value in _walk_values(payload):
        normalized = key.lower().replace(" ", "_").replace("-", "_")
        if normalized in wanted and not isinstance(value, (Mapping, list)):
            return value
    return None


def _provider_status_summary(payload: Mapping[str, Any]) -> dict[str, Any]:
    summary = {
        "provider": _first_scalar(payload, ["provider", "provider_name", "source"]) or "unknown",
        "status": _first_scalar(payload, ["status", "overall_status", "alpha_vantage_status"]) or "unknown",
        "configured": _first_scalar(payload, ["configured", "can_read"]),
        "enabled": _first_scalar(payload, ["enabled"]),
        "row_count": _first_scalar(payload, ["row_count", "rows", "returned_count"]),
        "last_success_time": _first_scalar(payload, ["last_success_time", "last_success_at"]),
        "message_zh": _first_scalar(payload, ["message_zh", "error_message_zh", "reason_zh"]),
    }
    return {key: value for key, value in sanitize_mapping(summary).items() if value not in (None, "")}


def _load_data_source_status() -> tuple[dict[str, Any], list[str]]:
    canonical = build_canonical_provider_status()
    providers = canonical.get("providers") if isinstance(canonical, Mapping) else {}
    if isinstance(providers, Mapping):
        paths = list(canonical.get("source_files") or [])
        paths.append(str(_out() / "provider_status_canonical.json"))
        normalized = {str(key): dict(value) for key, value in providers.items() if isinstance(value, Mapping)}
        legacy_aliases = {
            "tushare": "tushare_provider_status",
            "managed_proxy": "managed_proxy_status",
            "alpha_vantage": "fx_macro_provider_status",
            "newsapi": "news_provider_status",
            "shfe_public": "shfe_public_provider_status",
            "lme_tin": "lme_tin_provider_status",
        }
        for canonical_key, legacy_key in legacy_aliases.items():
            if canonical_key in normalized and legacy_key not in normalized:
                normalized[legacy_key] = dict(normalized[canonical_key])
        return normalized, paths

    statuses: dict[str, Any] = {}
    paths: list[str] = []
    base = _out()
    for source_id, parts in DATA_SOURCE_STATUS_FILES:
        path = base.joinpath(*parts)
        payload = _read_json(path)
        if isinstance(payload, Mapping):
            statuses[source_id] = _provider_status_summary(payload)
            paths.append(str(path))
    return statuses, paths


def _candidate_versions() -> list[str]:
    versions: set[str] = set()
    registry = _out() / "model_registry"
    for path in registry.glob("*v*.json") if registry.exists() else []:
        text = path.stem.lower()
        for token in ("v1", "v2", "v3", "v4", "v5", "v6"):
            if token in text:
                versions.add(token)
    for path in (_out() / "feature_store").glob("v*") if (_out() / "feature_store").exists() else []:
        if path.is_dir():
            versions.add(path.name.lower())
    ordered = sorted(versions, key=lambda item: int(item[1:]) if item.startswith("v") and item[1:].isdigit() else 0, reverse=True)
    return ordered or ["v5", "v4", "v3", "v2", "v1"]


def _latest_existing(paths: Iterable[Path]) -> tuple[Path | None, Any]:
    candidates = [path for path in paths if path.exists()]
    if not candidates:
        return None, None
    path = max(candidates, key=lambda item: item.stat().st_mtime)
    return path, _read_json(path)


def _merge_feature_stability(validation: Any, evidence: Mapping[str, Any]) -> dict[str, Any]:
    out = dict(validation) if isinstance(validation, Mapping) else {}
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
    return out


def _load_context() -> dict[str, Any]:
    versions = _candidate_versions()
    candidate_version = versions[0]
    model_registry = _out() / "model_registry"
    promotion_path, promotion = _latest_existing(
        [
            model_registry / f"promotion_report_{version}.json"
            for version in versions
        ]
        + [
            model_registry / "promotion_report.json",
            model_registry / "candidate_rejected.json",
        ]
    )
    validation_path, validation = _latest_existing(
        [_out() / "institutional_validation" / f"institutional_validation_report_{version}.json" for version in versions]
    )
    registry_path, registry = _latest_existing(
        [model_registry / f"candidate_{version}_model_registry.json" for version in versions]
        + [model_registry / "candidate_model_registry.json"]
    )
    oof_path, oof = _latest_existing(
        [_out() / "oof_integrity" / version / "oof_integrity_report.json" for version in versions]
    )
    backtest_path, backtest = _latest_existing(
        [
            _out() / "research_backtests" / version / "metrics_1d.json"
            for version in versions
        ]
    )
    feature_store_path, feature_store = _latest_existing(
        [_out() / "feature_store" / version / "feature_store_manifest.json" for version in versions]
    )
    coverage_path, coverage = _latest_existing(
        [
            _out() / "feature_coverage_report_v2.json",
            _out() / "feature_coverage_report.json",
        ]
    )
    active_path = model_registry / "active_model.json"
    active_model = _read_json(active_path)
    data_source_status, data_source_paths = _load_data_source_status()
    try:
        feature_stability = build_feature_stability_evidence(candidate_version=candidate_version)
    except Exception:
        feature_stability = {}
    validation_payload = validation if isinstance(validation, Mapping) else {}
    if isinstance(feature_stability, Mapping):
        validation_payload = _merge_feature_stability(validation_payload, feature_stability)
    return {
        "candidate_version": candidate_version,
        "active_path": active_path,
        "active_model": active_model,
        "promotion_path": promotion_path,
        "promotion": promotion if isinstance(promotion, Mapping) else {},
        "validation_path": validation_path,
        "validation": validation_payload,
        "feature_stability_path": model_registry / f"feature_stability_report_{candidate_version}.json",
        "feature_stability": feature_stability if isinstance(feature_stability, Mapping) else {},
        "registry_path": registry_path,
        "registry": registry if isinstance(registry, Mapping) else {},
        "oof_path": oof_path,
        "oof": oof if isinstance(oof, Mapping) else {},
        "backtest_path": backtest_path,
        "backtest": backtest if isinstance(backtest, Mapping) else {},
        "feature_store_path": feature_store_path,
        "feature_store": feature_store if isinstance(feature_store, Mapping) else {},
        "coverage_path": coverage_path,
        "coverage": coverage if isinstance(coverage, Mapping) else {},
        "data_source_status": data_source_status,
        "data_source_paths": data_source_paths,
    }


def _as_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except Exception:
        return None
    return parsed if parsed == parsed and parsed not in {float("inf"), float("-inf")} else None


def _first_number(payloads: Iterable[Any], key_names: Iterable[str]) -> float | None:
    wanted = {key.lower() for key in key_names}
    for payload in payloads:
        for key, value in _walk_values(payload):
            normalized = key.lower().replace(" ", "_").replace("-", "_")
            if normalized in wanted:
                number = _as_float(value)
                if number is not None:
                    return number
    return None


def _nested_cost_expectancy(payloads: Iterable[Any], multiplier: str) -> float | None:
    for payload in payloads:
        for key, value in _walk_values(payload):
            if str(key).lower() in {multiplier.lower(), f"{multiplier.lower()}x"} and isinstance(value, Mapping):
                number = _first_number([value], ["expectancy", "cost_adjusted_expectancy"])
                if number is not None:
                    return number
    return None


def _gate_value(promotion: Mapping[str, Any], name_fragment: str) -> float | None:
    rows = promotion.get("gate_results") or promotion.get("checks") or promotion.get("rules")
    if not isinstance(rows, list):
        return None
    fragment = name_fragment.lower()
    for row in rows:
        if not isinstance(row, Mapping):
            continue
        name = str(row.get("name") or row.get("rule") or "").lower()
        if fragment in name:
            return _as_float(row.get("value") or row.get("metric_value"))
    return None


def _group_coverage(feature_store: Mapping[str, Any], coverage: Mapping[str, Any]) -> dict[str, float]:
    raw = feature_store.get("group_coverage")
    if not isinstance(raw, Mapping):
        raw = {}
    out: dict[str, float] = {}
    for key, value in raw.items():
        number = _as_float(value)
        if number is not None:
            out[str(key)] = number

    groups = coverage.get("groups")
    if isinstance(groups, list):
        for group in groups:
            if not isinstance(group, Mapping):
                continue
            name = str(group.get("group") or "")
            number = _as_float(group.get("coverage_rate"))
            if name and number is not None:
                out.setdefault(name, number)
    return out


def _high_confidence_sample_count(oof: Mapping[str, Any]) -> int:
    horizons = oof.get("horizons")
    if not isinstance(horizons, Mapping):
        return 0
    counts: list[int] = []
    for horizon_payload in horizons.values():
        if not isinstance(horizon_payload, Mapping):
            continue
        confidence_subset = horizon_payload.get("confidence_subset")
        if not isinstance(confidence_subset, Mapping):
            continue
        for key in ("top20", "top_20", "top_20pct", "top_20_percent"):
            row = confidence_subset.get(key)
            if isinstance(row, Mapping):
                value = _as_float(row.get("sample_count"))
                if value is not None:
                    counts.append(int(value))
    return min(counts) if counts else 0


def _feature_stability_score(validation: Mapping[str, Any]) -> float | None:
    stability = validation.get("feature_stability")
    if isinstance(stability, Mapping):
        number = _first_number([stability], ["stability_score", "feature_stability_score"])
        if number is not None:
            return number
        if stability.get("passed") is False:
            return 0.0
    return _first_number([validation], ["feature_stability_score", "importance_stability"])


def _metric(value: float | None, threshold: float, passed: bool, message_zh: str) -> dict[str, Any]:
    return {
        "value": value,
        "threshold": threshold,
        "passed": bool(passed),
        "message_zh": message_zh,
    }


def _build_blocking_metrics(ctx: Mapping[str, Any]) -> dict[str, Any]:
    payloads = [ctx.get("promotion") or {}, ctx.get("validation") or {}, ctx.get("backtest") or {}, ctx.get("oof") or {}]
    pbo = _gate_value(ctx["promotion"], "pbo") or _first_number(payloads, ["pbo", "probability_of_backtest_overfitting"])
    dsr = _first_number(payloads, ["deflated_sharpe_ratio", "dsr"])
    worst_fold = _gate_value(ctx["promotion"], "worst_fold") or _first_number(payloads, ["worst_fold_accuracy"])
    worst_year = _first_number(payloads, ["worst_year_accuracy"])
    worst_regime = _first_number(payloads, ["worst_regime_accuracy"])
    cost_2x = _gate_value(ctx["promotion"], "2x") or _nested_cost_expectancy(payloads, "2x")
    cost_3x = _nested_cost_expectancy(payloads, "3x")
    max_drawdown = _first_number(payloads, ["max_drawdown", "max_drawdown_proxy"])
    turnover = _first_number(payloads, ["turnover", "turnover_proxy"])
    high_conf_count = _high_confidence_sample_count(ctx["oof"])
    feature_stability = _feature_stability_score(ctx["validation"])
    group_cov = _group_coverage(ctx["feature_store"], ctx["coverage"])
    missing_groups = [group for group in MISSING_FUNDAMENTAL_GROUPS if group_cov.get(group, 0.0) < 0.2]
    reality_pass = None
    for _, value in _walk_values(ctx["validation"]):
        if isinstance(value, bool):
            continue
    reality_raw = ctx["validation"].get("reality_check_pass") if isinstance(ctx["validation"], Mapping) else None
    if reality_raw is None:
        metrics = ctx["validation"].get("metrics") if isinstance(ctx["validation"], Mapping) else {}
        if isinstance(metrics, Mapping):
            reality_raw = metrics.get("reality_check_pass")
    if isinstance(reality_raw, bool):
        reality_pass = reality_raw

    return sanitize_for_json(
        {
            "candidate_version": ctx.get("candidate_version") or "v5",
            "pbo": _metric(pbo, DEFAULT_THRESHOLDS["pbo"], pbo is not None and pbo < DEFAULT_THRESHOLDS["pbo"], "PBO must stay below overfitting threshold."),
            "dsr": _metric(dsr, DEFAULT_THRESHOLDS["dsr"], dsr is not None and dsr > DEFAULT_THRESHOLDS["dsr"], "DSR must be positive after deflation."),
            "reality_check": {"passed": bool(reality_pass), "value": reality_pass, "message_zh": "Reality Check must pass bootstrap significance."},
            "worst_fold_accuracy": _metric(worst_fold, DEFAULT_THRESHOLDS["worst_fold_accuracy"], worst_fold is not None and worst_fold >= DEFAULT_THRESHOLDS["worst_fold_accuracy"], "Worst fold must stay above stability floor."),
            "worst_year_accuracy": _metric(worst_year, DEFAULT_THRESHOLDS["worst_year_accuracy"], worst_year is not None and worst_year >= DEFAULT_THRESHOLDS["worst_year_accuracy"], "Worst year must not collapse."),
            "worst_regime_accuracy": _metric(worst_regime, DEFAULT_THRESHOLDS["worst_regime_accuracy"], worst_regime is not None and worst_regime >= DEFAULT_THRESHOLDS["worst_regime_accuracy"], "Worst regime must not collapse."),
            "cost_stress_2x_expectancy": _metric(cost_2x, DEFAULT_THRESHOLDS["cost_stress_2x_expectancy"], cost_2x is not None and cost_2x >= 0.0, "2x cost stress must be non-negative."),
            "cost_stress_3x_expectancy": _metric(cost_3x, DEFAULT_THRESHOLDS["cost_stress_3x_expectancy"], cost_3x is not None and cost_3x >= 0.0, "3x cost stress should not be deeply negative."),
            "max_drawdown": _metric(max_drawdown, DEFAULT_THRESHOLDS["max_drawdown"], max_drawdown is not None and max_drawdown <= DEFAULT_THRESHOLDS["max_drawdown"], "Drawdown must remain within risk budget."),
            "turnover": {"value": turnover, "message_zh": "High turnover increases slippage sensitivity."},
            "high_confidence_sample_count": _metric(float(high_conf_count), DEFAULT_THRESHOLDS["high_confidence_sample_count"], high_conf_count >= DEFAULT_THRESHOLDS["high_confidence_sample_count"], "High-confidence subsets need enough OOF samples."),
            "feature_stability_score": _metric(feature_stability, DEFAULT_THRESHOLDS["feature_stability_score"], feature_stability is not None and feature_stability >= DEFAULT_THRESHOLDS["feature_stability_score"], "Feature importance must be stable across folds."),
            "group_coverage": group_cov,
            "missing_factor_groups": missing_groups,
            "data_source_status": ctx.get("data_source_status") or {},
        }
    )


def _cause(category: str, severity: str, evidence: str, fix_plan: str) -> dict[str, str]:
    return {
        "category": category,
        "severity": severity,
        "evidence": sanitize_text(evidence),
        "fix_plan": sanitize_text(fix_plan),
    }


def _build_root_causes(metrics: Mapping[str, Any], ctx: Mapping[str, Any]) -> list[dict[str, str]]:
    causes: list[dict[str, str]] = []
    missing_groups = metrics.get("missing_factor_groups") if isinstance(metrics.get("missing_factor_groups"), list) else []
    if missing_groups:
        data_sources = metrics.get("data_source_status") if isinstance(metrics.get("data_source_status"), Mapping) else {}
        source_bits = [
            f"{name}={payload.get('status')}"
            for name, payload in data_sources.items()
            if isinstance(payload, Mapping) and payload.get("status") not in {"success", "available", "using_cache"}
        ]
        source_evidence = f" Data source blockers: {', '.join(source_bits)}." if source_bits else ""
        causes.append(
            _cause(
                "data_coverage",
                "P0",
                f"Missing or low-coverage factor groups: {', '.join(str(item) for item in missing_groups)}.{source_evidence}",
                "Prioritize Tushare/managed proxy/cross-market/event real-field backfill before expecting stable active promotion.",
            )
        )
    pbo = metrics["pbo"]
    dsr = metrics["dsr"]
    reality = metrics["reality_check"]
    if not pbo.get("passed") or not dsr.get("passed") or not reality.get("passed"):
        causes.append(
            _cause(
                "overfitting",
                "P0",
                f"PBO={pbo.get('value')}, DSR={dsr.get('value')}, RealityCheck={reality.get('value')}.",
                "Reduce experiment selection bias, use stricter purged validation, and prefer simpler stable ensembles until DSR/PBO recover.",
            )
        )
    worst_fold = metrics["worst_fold_accuracy"]
    worst_year = metrics["worst_year_accuracy"]
    worst_regime = metrics["worst_regime_accuracy"]
    if not worst_fold.get("passed") or not worst_year.get("passed") or not worst_regime.get("passed"):
        causes.append(
            _cause(
                "model_stability",
                "P0",
                f"Worst fold/year/regime accuracy: {worst_fold.get('value')}/{worst_year.get('value')}/{worst_regime.get('value')}.",
                "Diagnose fold/year/regime failure buckets, add no-trade guards, and avoid models whose gains concentrate in one period.",
            )
        )
    cost_2x = metrics["cost_stress_2x_expectancy"]
    cost_3x = metrics["cost_stress_3x_expectancy"]
    if not cost_2x.get("passed") or not cost_3x.get("passed"):
        causes.append(
            _cause(
                "cost",
                "P1",
                f"2x/3x cost expectancy: {cost_2x.get('value')}/{cost_3x.get('value')}.",
                "Optimize for cost-adjusted expectancy, reduce turnover, and require stronger trade_edge before selecting signals.",
            )
        )
    drawdown = metrics["max_drawdown"]
    if not drawdown.get("passed"):
        causes.append(
            _cause(
                "risk",
                "P1",
                f"Max drawdown proxy={drawdown.get('value')} exceeds threshold={drawdown.get('threshold')}.",
                "Add high-volatility drawdown guards, event-shock no-trade filters, and horizon-level allocation caps.",
            )
        )
    high_conf = metrics["high_confidence_sample_count"]
    if not high_conf.get("passed"):
        causes.append(
            _cause(
                "sample_size",
                "P1",
                f"High-confidence OOF sample count={high_conf.get('value')} below threshold={high_conf.get('threshold')}.",
                "Do not market high-confidence accuracy until OOF sample counts and fold coverage are sufficient.",
            )
        )
    stability = metrics["feature_stability_score"]
    if not stability.get("passed"):
        causes.append(
            _cause(
                "feature_stability",
                "P1",
                f"Feature stability score={stability.get('value')} below threshold={stability.get('threshold')}.",
                "Blacklist unstable high-importance features and prefer fold-stable technical/fundamental features.",
            )
        )
    promotion = ctx.get("promotion") if isinstance(ctx.get("promotion"), Mapping) else {}
    if promotion and not bool(promotion.get("promotion_gate_passed") or promotion.get("gate_passed")):
        causes.append(
            _cause(
                "validation",
                "P0",
                f"Latest promotion report status={promotion.get('status') or promotion.get('promotion_status') or 'failed'}; blocking reasons={promotion.get('blocking_reasons') or []}.",
                "Keep active disabled until all hard promotion gates pass and a human approval step is completed.",
            )
        )
    if not causes:
        causes.append(
            _cause(
                "validation",
                "P2",
                "No active_model.json is present and no passing promotion report was found.",
                "Run institutional validation and promotion dry-run after real incremental features are available.",
            )
        )
    return causes


def _candidate_v6_plan(metrics: Mapping[str, Any]) -> dict[str, Any]:
    missing = metrics.get("missing_factor_groups") if isinstance(metrics.get("missing_factor_groups"), list) else []
    return {
        "status": "research_plan_only",
        "candidate_version": "v6",
        "auto_publish_active": False,
        "customer_prediction_generated": False,
        "data_repair_priority": [
            "Backfill real open_interest/settlement/warehouse/holding via Tushare when token is available.",
            "Use managed proxy for spot/basis/inventory/LME/term structure where public sources remain unavailable.",
            f"Current missing groups: {', '.join(str(item) for item in missing) or 'none detected'}",
        ],
        "label_governance": [
            "Keep direction_thresholded and volatility-adjusted labels to reduce low-return noise.",
            "Audit triple-barrier ATR labels by fold and remove horizons where no-trade class dominates.",
            "Record label distribution and no-lookahead checks before any candidate training.",
        ],
        "model_family_plan": [
            "Prefer compact HistGradientBoosting/ExtraTrees ensembles with fold-stability constraints.",
            "Use LightGBM only when feature coverage and fold stability justify it.",
            "Keep linear models as internal diagnostics only; do not expose them as prediction output.",
        ],
        "risk_controls": [
            "Increase min_trade_edge under high volatility and stale cross-market data.",
            "Apply event-shock and high-volatility no-trade guards.",
            "Reject strategies where one fold/year/regime dominates performance.",
        ],
        "multi_objective_optimization": [
            "Maximize cost-adjusted expectancy, top20 OOF accuracy, DSR, and feature stability.",
            "Minimize max drawdown, PBO, turnover, and concentration risk.",
            "Select thresholds inside training folds only; validation folds remain evaluation-only.",
        ],
        "minimum_go_live_gates": [
            "promotion dry-run pass",
            "institutional validation pass",
            "DSR > 0",
            "PBO < 0.20",
            "Reality Check pass",
            "2x cost stress non-negative",
            "worst fold/year/regime accuracy >= 0.52",
            "feature stability score >= 0.55",
            "no mock/sample data",
            "human approval phrase required",
        ],
        "needed_data_sources": [
            "Tushare token for futures daily/open_interest/settlement/warehouse/holding.",
            "Managed proxy or formal vendor for spot/basis/inventory/LME/term structure.",
            "Alpha Vantage cache for USD/CNY and US10Y, with rate-limit backfill.",
            "NewsAPI high-evidence tin industry events only when used_in_model=true.",
        ],
    }


def build_active_absence_diagnostics() -> dict[str, Any]:
    """Explain why no active model is publishable without changing model state."""

    ctx = _load_context()
    active_payload = ctx.get("active_model")
    active_exists = isinstance(active_payload, Mapping) and bool(active_payload)
    metrics = _build_blocking_metrics(ctx)
    root_causes = [] if active_exists else _build_root_causes(metrics, ctx)
    report = {
        "generated_at": _now(),
        "active_status": "available" if active_exists else "none",
        "active_model_path": str(ctx["active_path"]) if active_exists else "",
        "candidate_version": metrics.get("candidate_version", ctx.get("candidate_version") or "v5"),
        "root_causes": root_causes,
        "blocking_metrics": metrics,
        "candidate_v6_plan": _candidate_v6_plan(metrics),
        "data_source_status": ctx.get("data_source_status") or {},
        "feature_stability_evidence": ctx.get("feature_stability") or {},
        "source_files": {
            "promotion": str(ctx["promotion_path"]) if ctx.get("promotion_path") else "",
            "institutional_validation": str(ctx["validation_path"]) if ctx.get("validation_path") else "",
            "feature_stability": str(ctx["feature_stability_path"]) if ctx.get("feature_stability_path") else "",
            "candidate_registry": str(ctx["registry_path"]) if ctx.get("registry_path") else "",
            "oof_integrity": str(ctx["oof_path"]) if ctx.get("oof_path") else "",
            "research_backtest": str(ctx["backtest_path"]) if ctx.get("backtest_path") else "",
            "feature_store_manifest": str(ctx["feature_store_path"]) if ctx.get("feature_store_path") else "",
            "feature_coverage": str(ctx["coverage_path"]) if ctx.get("coverage_path") else "",
            "data_source_status": ctx.get("data_source_paths") or [],
        },
        "active_updated": False,
        "customer_prediction_generated": False,
        "baseline_used": False,
        "fake_prediction_generated": False,
        "message_zh": "当前没有可发布 active model；本报告只做根因诊断和 candidate_v6 研究计划，不发布 active，不生成客户预测。",
    }
    path = _out() / "model_registry" / "active_absence_diagnostics.json"
    _write_json(path, report)
    report["report_path"] = str(path)
    return sanitize_for_json(sanitize_mapping(report))
