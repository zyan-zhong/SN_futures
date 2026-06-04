from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

import numpy as np

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .candidate_v7_research_service import DEFAULT_HORIZONS, _normalise_horizons
from .cpcv_validation_service import build_cpcv_report
from .institutional_validation_service import run_institutional_validation
from .model_promotion_service import promote_candidate
from .research_backtest_service import run_research_backtest
from .walk_forward_training_service import run_candidate_training
from .cost_stress_attribution_service import get_candidate_report_with_cost_attribution
from .year_concentration_service import build_year_evidence_summary, get_candidate_report_with_year_evidence


CANDIDATE_VERSION = "v12"
DATASET_VERSION = "v12"
FEATURE_STORE_VERSION = "v12"
FEATURE_SET = "managed_proxy_pit_candidate_v12"
REQUIRED_HORIZONS = ("1d", "3d", "5d", "10d", "20d")
LABEL_VARIANTS = (
    "direction_thresholded",
    "volatility_adjusted_direction",
    "triple_barrier_atr",
    "meta_label_tradeability",
)
MODELS = ("sklearn_hist_gradient", "extra_trees", "random_forest")
CALIBRATION = ("sigmoid",)
NO_TRADE_FILTERS = (
    "low_confidence",
    "low_edge",
    "high_cost_pressure",
    "stale_data",
    "low_liquidity",
    "roll_period",
    "drawdown_guard",
    "regime_guard",
    "fold_trade_quota",
    "year_trade_quota",
    "managed_pit_guard",
)


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _output_dir() -> Path:
    return get_user_output_dir()


def _research_dir() -> Path:
    path = _output_dir() / "model_research" / "candidate_v12"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _report_path() -> Path:
    return _research_dir() / "candidate_v12_gated_research_report.json"


def _training_dataset_manifest_path() -> Path:
    return _output_dir() / "training_dataset_manifest_v12.json"


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


def _nested(payload: Mapping[str, Any], *keys: str) -> Any:
    current: Any = payload
    for key in keys:
        if not isinstance(current, Mapping):
            return None
        current = current.get(key)
    return current


def load_training_dataset_v12_manifest() -> dict[str, Any] | None:
    payload = _read_json(_training_dataset_manifest_path())
    return dict(payload) if isinstance(payload, Mapping) else None


def load_training_dataset_v12_paths(manifest: Mapping[str, Any] | None = None) -> dict[str, str]:
    manifest = manifest or load_training_dataset_v12_manifest() or {}
    paths = manifest.get("dataset_paths")
    if not isinstance(paths, Mapping):
        return {}
    return {str(key): str(value) for key, value in paths.items() if value}


def _check(name: str, passed: bool, value: Any = None, reason: str | None = None) -> dict[str, Any]:
    return {"passed": bool(passed), "value": value, "reason": "" if passed else str(reason or name)}


def validate_candidate_v12_readiness() -> dict[str, Any]:
    manifest = load_training_dataset_v12_manifest()
    checks: dict[str, dict[str, Any]] = {}
    blocking: list[str] = []

    if manifest is None:
        checks["training_dataset_manifest"] = _check("training_dataset_manifest", False, str(_training_dataset_manifest_path()), "training_dataset_v12_manifest_missing")
        blocking.append("training_dataset_v12_manifest_missing")
        manifest = {}
    else:
        checks["training_dataset_manifest"] = _check("training_dataset_manifest", True, str(_training_dataset_manifest_path()))

    dataset_status = str(manifest.get("status") or "missing").lower()
    dataset_ready = dataset_status in {"ready", "success"}
    checks["training_dataset_status"] = _check("training_dataset_status", dataset_ready, dataset_status, "training_dataset_v12_blocked")
    if not dataset_ready:
        blocking.append("training_dataset_v12_blocked")
        blocking.extend(str(item) for item in manifest.get("blocked_reasons", []) if item)

    dataset_version = str(manifest.get("dataset_version") or "").lower()
    checks["dataset_version"] = _check("dataset_version", dataset_version == DATASET_VERSION, dataset_version, "training_dataset_not_v12")
    if dataset_version and dataset_version != DATASET_VERSION:
        blocking.append("training_dataset_not_v12")

    feature_store_version = str(manifest.get("feature_store_version") or "").lower()
    checks["feature_store_version"] = _check("feature_store_version", feature_store_version == FEATURE_STORE_VERSION, feature_store_version, "feature_store_not_v12")
    if feature_store_version and feature_store_version != FEATURE_STORE_VERSION:
        blocking.append("feature_store_not_v12")

    feature_store_status = str(manifest.get("feature_store_status") or "missing").lower()
    feature_store_ready = feature_store_status in {"ready", "success"}
    checks["feature_store_status"] = _check("feature_store_status", feature_store_ready, feature_store_status, "feature_store_v12_blocked")
    if not feature_store_ready:
        blocking.append("feature_store_v12_blocked")

    paths = load_training_dataset_v12_paths(manifest)
    missing_horizons = [horizon for horizon in REQUIRED_HORIZONS if horizon not in paths]
    missing_files = [horizon for horizon, path in paths.items() if not Path(path).is_file()]
    paths_ready = not missing_horizons and not missing_files
    checks["dataset_paths"] = _check(
        "dataset_paths",
        paths_ready,
        {"available": sorted(paths), "missing_horizons": missing_horizons, "missing_files": missing_files},
        "training_dataset_v12_paths_missing",
    )
    if missing_horizons or not paths:
        blocking.append("training_dataset_v12_paths_missing")
    if missing_files:
        blocking.append("training_dataset_v12_path_file_missing")

    no_lookahead = bool(manifest.get("no_lookahead_pass"))
    checks["no_lookahead_pass"] = _check("no_lookahead_pass", no_lookahead, no_lookahead, "training_dataset_v12_no_lookahead_failed")
    if not no_lookahead:
        blocking.append("training_dataset_v12_no_lookahead_failed")

    pit_ready = bool(manifest.get("point_in_time_join_ready"))
    checks["point_in_time_join_ready"] = _check("point_in_time_join_ready", pit_ready, pit_ready, "training_dataset_v12_pit_not_ready")
    if not pit_ready:
        blocking.append("training_dataset_v12_pit_not_ready")

    candidate_allowed = bool(manifest.get("candidate_v12_allowed"))
    checks["candidate_v12_allowed"] = _check("candidate_v12_allowed", candidate_allowed, candidate_allowed, "candidate_v12_not_allowed_by_dataset")
    if not candidate_allowed:
        blocking.append("candidate_v12_not_allowed_by_dataset")

    managed_used = bool(manifest.get("managed_data_used"))
    checks["managed_data_used"] = _check("managed_data_used", managed_used, managed_used, "managed_data_not_used")
    if not managed_used:
        blocking.append("managed_data_not_used")

    for key, reason in (
        ("fake_data_used", "fake_data_used"),
        ("mock_data_used", "mock_data_used"),
        ("sample_data_used", "sample_data_used"),
        ("baseline_used", "baseline_used"),
    ):
        used = bool(manifest.get(key))
        checks[key] = _check(key, not used, used, reason)
        if used:
            blocking.append(reason)

    return sanitize_for_json(
        {
            "status": "ready" if not blocking else "blocked",
            "candidate_version": CANDIDATE_VERSION,
            "dataset_version": DATASET_VERSION,
            "feature_store_version": FEATURE_STORE_VERSION,
            "training_dataset_status": dataset_status,
            "feature_store_status": feature_store_status,
            "readiness_checks": checks,
            "dataset_paths": paths,
            "blocking_reasons": sorted(set(blocking)),
            "training_dataset_manifest_path": str(_training_dataset_manifest_path()),
            "training_dataset_manifest": manifest,
        }
    )


def run_candidate_v12_research_training(
    *,
    horizons: tuple[str, ...],
    dataset_version: str,
    feature_store_version: str,
) -> dict[str, Any]:
    return run_candidate_training(
        horizons=horizons,
        candidate_version=CANDIDATE_VERSION,
        dataset_version=dataset_version,
        feature_set=FEATURE_SET,
        label_variants=LABEL_VARIANTS,
        models=MODELS,
        calibration=CALIBRATION,
        no_trade_filters=NO_TRADE_FILTERS,
    )


def build_candidate_v12_oof_trace(*, horizons: tuple[str, ...]) -> dict[str, Any]:
    base = _output_dir() / "walk_forward" / CANDIDATE_VERSION
    paths = sorted(str(path) for path in base.glob("oof_trace_*.csv")) if base.exists() else []
    return {
        "status": "success" if paths else "missing",
        "oof_trace_path": paths[0] if paths else "",
        "oof_trace_paths": paths,
        "horizons": list(horizons),
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def run_candidate_v12_cpcv_validation() -> dict[str, Any]:
    payload = build_cpcv_report(candidate_version=CANDIDATE_VERSION)
    return dict(payload) if isinstance(payload, Mapping) else {"status": "failed"}


def run_candidate_v12_institutional_validation() -> dict[str, Any]:
    payload = run_institutional_validation(candidate_version=CANDIDATE_VERSION, dry_run=True)
    return dict(payload) if isinstance(payload, Mapping) else {"status": "failed"}


def run_candidate_v12_promotion_dry_run() -> dict[str, Any]:
    payload = promote_candidate(candidate_version=CANDIDATE_VERSION, dry_run=True)
    return dict(payload) if isinstance(payload, Mapping) else {"status": "failed", "passed": False}


def _candidate_v10_baseline() -> dict[str, Any]:
    report = _read_json(_output_dir() / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json")
    if isinstance(report, Mapping):
        comparison = report.get("v10_vs_v9")
        if isinstance(comparison, Mapping) and isinstance(comparison.get("v10"), Mapping):
            return dict(comparison["v10"])
    return {
        "PBO": 1.0,
        "Reality Check p-value": 1.0,
        "regime concentration": 1.0,
        "fold concentration": 1.0,
        "year concentration": 1.0,
        "2x cost expectancy": 0.0,
        "3x cost expectancy": 0.0,
    }


def _v12_metrics(cpcv: Mapping[str, Any], institutional: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "PBO": _safe_float(_nested(cpcv, "pbo", "pbo"), 1.0),
        "Reality Check p-value": _safe_float(_nested(cpcv, "reality_check", "aggregate_p_value"), 1.0),
        "regime concentration": _safe_float(_nested(institutional, "dominance_checks", "single_regime_contribution"), 1.0),
        "fold concentration": _safe_float(_nested(institutional, "dominance_checks", "single_fold_contribution"), 1.0),
        "year concentration": _safe_float(_nested(institutional, "dominance_checks", "single_year_contribution"), 1.0),
        "2x cost expectancy": _safe_float(_nested(institutional, "cost_stress", "2x_cost", "expectancy"), 0.0),
        "3x cost expectancy": _safe_float(_nested(institutional, "cost_stress", "3x_cost", "expectancy"), 0.0),
    }


def compare_v12_vs_v10(cpcv: Mapping[str, Any], institutional: Mapping[str, Any]) -> dict[str, Any]:
    before = _candidate_v10_baseline()
    after = _v12_metrics(cpcv, institutional)
    improvement = {
        "PBO": _safe_float(before.get("PBO"), 1.0) - _safe_float(after.get("PBO"), 1.0),
        "Reality Check p-value": _safe_float(before.get("Reality Check p-value"), 1.0) - _safe_float(after.get("Reality Check p-value"), 1.0),
        "regime concentration": _safe_float(before.get("regime concentration"), 1.0) - _safe_float(after.get("regime concentration"), 1.0),
        "fold concentration": _safe_float(before.get("fold concentration"), 1.0) - _safe_float(after.get("fold concentration"), 1.0),
        "year concentration": _safe_float(before.get("year concentration"), 1.0) - _safe_float(after.get("year concentration"), 1.0),
        "2x cost expectancy": _safe_float(after.get("2x cost expectancy"), 0.0) - _safe_float(before.get("2x cost expectancy"), 0.0),
        "3x cost expectancy": _safe_float(after.get("3x cost expectancy"), 0.0) - _safe_float(before.get("3x cost expectancy"), 0.0),
    }
    return {"v10": before, "v12": after, "improvement": improvement, "improvement_pass": any(value > 0 for value in improvement.values())}


def validate_candidate_v12_gate(
    *,
    cpcv_validation: Mapping[str, Any],
    institutional_validation: Mapping[str, Any],
    promotion_dry_run: Mapping[str, Any],
    v12_vs_v10: Mapping[str, Any],
) -> dict[str, Any]:
    pbo = _safe_float(_nested(cpcv_validation, "pbo", "pbo"), 1.0)
    reality_pass = bool(_nested(cpcv_validation, "reality_check", "passed"))
    two_x = _safe_float(_nested(institutional_validation, "cost_stress", "2x_cost", "expectancy"), 0.0)
    three_x = _safe_float(_nested(institutional_validation, "cost_stress", "3x_cost", "expectancy"), 0.0)
    regime = _safe_float(_nested(institutional_validation, "dominance_checks", "single_regime_contribution"), 1.0)
    fold = _safe_float(_nested(institutional_validation, "dominance_checks", "single_fold_contribution"), 1.0)
    year = _safe_float(_nested(institutional_validation, "dominance_checks", "single_year_contribution"), 1.0)
    checks = {
        "pbo": pbo,
        "pbo_lt_0_2": pbo < 0.2,
        "reality_check_pass": reality_pass,
        "two_x_cost_expectancy": two_x,
        "three_x_cost_expectancy": three_x,
        "institutional_cost_stress_pass": two_x > 0.0 and three_x > 0.0,
        "regime_concentration": regime,
        "regime_concentration_pass": regime <= 0.5,
        "fold_concentration": fold,
        "fold_concentration_pass": fold <= 0.5,
        "year_concentration": year,
        "year_concentration_evidence_present": _nested(institutional_validation, "dominance_checks", "single_year_contribution") is not None,
        "year_concentration_pass": year <= 0.5,
        "v12_vs_v10_improvement_pass": bool(v12_vs_v10.get("improvement_pass")),
        "promotion_dry_run_pass": bool(promotion_dry_run.get("passed")),
    }
    checks["gate_passed"] = bool(
        checks["pbo_lt_0_2"]
        and checks["reality_check_pass"]
        and checks["institutional_cost_stress_pass"]
        and checks["regime_concentration_pass"]
        and checks["fold_concentration_pass"]
        and checks["year_concentration_pass"]
        and checks["v12_vs_v10_improvement_pass"]
        and checks["promotion_dry_run_pass"]
    )
    return sanitize_for_json(checks)


def _skipped(name: str, reason: str) -> dict[str, Any]:
    return {"status": "skipped", "step": name, "skipped_reason": reason, "active_updated": False, "customer_prediction_generated": False}


def build_candidate_v12_report(
    *,
    status: str,
    readiness: Mapping[str, Any],
    horizons: tuple[str, ...],
    training: Mapping[str, Any] | None = None,
    oof: Mapping[str, Any] | None = None,
    cpcv: Mapping[str, Any] | None = None,
    institutional: Mapping[str, Any] | None = None,
    promotion: Mapping[str, Any] | None = None,
    v12_vs_v10: Mapping[str, Any] | None = None,
    gate_checks: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    training = training or {}
    blocked = sorted(set(str(item) for item in readiness.get("blocking_reasons", []) if item))
    skipped_reason = ";".join(blocked) if blocked else "not_run"
    oof = oof or _skipped("oof_trace", skipped_reason)
    cpcv = cpcv or _skipped("cpcv_validation", skipped_reason)
    institutional = institutional or _skipped("institutional_validation", skipped_reason)
    promotion = promotion or _skipped("promotion_dry_run", skipped_reason)
    v12_vs_v10 = v12_vs_v10 or {}
    gate_checks = gate_checks or {"gate_passed": False}
    if status == "success":
        year_evidence = build_year_evidence_summary(CANDIDATE_VERSION)
    else:
        year_evidence = build_year_evidence_summary(
            CANDIDATE_VERSION,
            skipped_reasons=[
                *(blocked or []),
                "candidate_v12_blocked" if status == "blocked" else "candidate_v12_not_success",
                "oof_trace_missing",
                "training_not_invoked",
            ],
        )
        gate_checks = {**dict(gate_checks), "year_concentration_pass": False, "year_concentration_evidence_present": False}
    training_dataset_manifest = readiness.get("training_dataset_manifest") if isinstance(readiness.get("training_dataset_manifest"), Mapping) else {}
    report = {
        "status": status,
        "generated_at": _now(),
        "candidate_version": CANDIDATE_VERSION,
        "dataset_version": DATASET_VERSION,
        "feature_store_version": FEATURE_STORE_VERSION,
        "feature_set": FEATURE_SET,
        "horizons": list(horizons),
        "training_dataset_status": readiness.get("training_dataset_status") or training_dataset_manifest.get("status") or "missing",
        "feature_store_status": readiness.get("feature_store_status") or training_dataset_manifest.get("feature_store_status") or "missing",
        "readiness_checks": readiness.get("readiness_checks") or {},
        "training_invoked": bool(training),
        "training_result": dict(training),
        "oof_trace_path": str(oof.get("oof_trace_path") or ""),
        "oof_trace_result": dict(oof),
        "cpcv_report_path": str(cpcv.get("report_path") or ""),
        "cpcv_validation": dict(cpcv),
        "pbo": _nested(cpcv, "pbo", "pbo"),
        "reality_check": cpcv.get("reality_check") if isinstance(cpcv.get("reality_check"), Mapping) else dict(cpcv),
        "institutional_validation": dict(institutional),
        "institutional_cost_stress": institutional.get("cost_stress") if isinstance(institutional.get("cost_stress"), Mapping) else {},
        "year_concentration_evidence": year_evidence,
        "regime_concentration": {
            "value": _nested(institutional, "dominance_checks", "single_regime_contribution"),
            "passed": bool(gate_checks.get("regime_concentration_pass")),
        },
        "fold_concentration": {
            "value": _nested(institutional, "dominance_checks", "single_fold_contribution"),
            "passed": bool(gate_checks.get("fold_concentration_pass")),
        },
        "v12_vs_v10": dict(v12_vs_v10),
        "gate_checks": dict(gate_checks),
        "blocking_reasons": [] if status == "success" else blocked,
        "manual_approval_recommended": bool(gate_checks.get("gate_passed")) if status == "success" else False,
        "promotion_dry_run_result": dict(promotion),
        "active_updated": False,
        "customer_prediction_generated": False,
        "fake_data_used": False,
        "mock_data_used": False,
        "report_path": str(_report_path()),
    }
    return _write_json(_report_path(), report)


def run_candidate_v12_research(
    *,
    horizons: Iterable[str] = DEFAULT_HORIZONS,
    build_missing: bool = False,
) -> dict[str, Any]:
    del build_missing  # Candidate v12 must not synthesize or fallback-build its prerequisites.
    horizon_list = tuple(_normalise_horizons(horizons))
    readiness = validate_candidate_v12_readiness()
    if readiness["status"] != "ready":
        return build_candidate_v12_report(status="blocked", readiness=readiness, horizons=horizon_list)

    training = run_candidate_v12_research_training(
        horizons=horizon_list,
        dataset_version=DATASET_VERSION,
        feature_store_version=FEATURE_STORE_VERSION,
    )
    oof = build_candidate_v12_oof_trace(horizons=horizon_list)
    cpcv = run_candidate_v12_cpcv_validation()
    research_backtest = run_research_backtest(candidate_version=CANDIDATE_VERSION, horizons=horizon_list)
    institutional = run_candidate_v12_institutional_validation()
    promotion = run_candidate_v12_promotion_dry_run()
    comparison = compare_v12_vs_v10(cpcv, institutional)
    gate_checks = validate_candidate_v12_gate(
        cpcv_validation=cpcv,
        institutional_validation=institutional,
        promotion_dry_run=promotion,
        v12_vs_v10=comparison,
    )
    report = build_candidate_v12_report(
        status="success" if bool(gate_checks.get("gate_passed")) else "failed",
        readiness=readiness,
        horizons=horizon_list,
        training=training,
        oof=oof,
        cpcv=cpcv,
        institutional={**institutional, "research_backtest": research_backtest},
        promotion=promotion,
        v12_vs_v10=comparison,
        gate_checks=gate_checks,
    )
    report["training_invoked"] = True
    _write_json(_report_path(), report)
    return sanitize_for_json(report)


def get_candidate_v12_report() -> dict[str, Any]:
    payload = _read_json(_report_path())
    if isinstance(payload, Mapping):
        return get_candidate_report_with_cost_attribution(CANDIDATE_VERSION)
    readiness = validate_candidate_v12_readiness()
    return build_candidate_v12_report(status="not_run", readiness=readiness, horizons=tuple(DEFAULT_HORIZONS))
