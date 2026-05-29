from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Mapping

from ..api.json_utils import sanitize_for_json
from ..runtime import get_user_output_dir
from .cross_market_feature_join_service import CROSS_MARKET_VALUE_FIELDS
from .feature_store_service import EVENT_FACTOR_INPUT_FIELDS, build_feature_store, get_feature_store_status
from .institutional_validation_service import run_institutional_validation
from .model_promotion_service import promote_candidate
from .oof_integrity_service import get_oof_integrity_report
from .research_artifact_service import archive_research_run
from .research_backtest_service import run_research_backtest
from .research_strategy_optimizer import optimize_research_strategy
from .training_dataset_service import build_training_dataset, get_training_dataset_status
from .walk_forward_training_service import run_candidate_training


DEFAULT_HORIZONS = ("1d", "3d", "5d", "10d", "20d")
V4_FEATURE_SET = "ohlcv_technical_regime_cross_market_event"
V4_LABEL_VARIANTS = ("direction_thresholded", "volatility_adjusted_direction", "triple_barrier_atr")
V4_MODELS = ("lightgbm_gbdt", "hist_gradient_boosting", "extra_trees", "random_forest")
V4_CALIBRATION = ("sigmoid", "isotonic")
V4_NO_TRADE_FILTERS = (
    "low_confidence",
    "low_edge",
    "high_volatility",
    "event_shock",
    "rate_limit_stale_data_guard",
    "roll_period",
)
BLOCKED_REASON_ZH = "没有真实新增 cross-market 或 event 字段，未训练 candidate_v4。"


def _output_dir() -> Path:
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
    path.write_text(json.dumps(sanitize_for_json(dict(payload)), ensure_ascii=False, indent=2), encoding="utf-8")


def _readiness_path() -> Path:
    return _output_dir() / "feature_store" / "v4" / "v4_readiness.json"


def _split_incremental_fields(manifest: Mapping[str, Any]) -> tuple[list[str], list[str], list[str]]:
    usable = {str(item) for item in manifest.get("usable_fields") or []}
    cross_market = sorted(usable.intersection(str(item) for item in CROSS_MARKET_VALUE_FIELDS))
    event = sorted(usable.intersection(str(item) for item in EVENT_FACTOR_INPUT_FIELDS))
    incremental = sorted(set(cross_market + event))
    return cross_market, event, incremental


def _excluded_reasons(manifest: Mapping[str, Any]) -> tuple[list[str], dict[str, str]]:
    excluded = [str(item) for item in manifest.get("excluded_fields") or []]
    reasons = {str(key): str(value) for key, value in dict(manifest.get("exclusion_reasons") or {}).items()}
    return excluded, reasons


def check_feature_store_v4_readiness(*, build_if_missing: bool = True) -> dict[str, Any]:
    """Gate v4 on real incremental cross-market or event fields.

    v4 should not train a new candidate unless Prompt 61S/62S produced at least
    one usable incremental field beyond the OHLCV/technical feature set.
    """

    manifest = get_feature_store_status(version="v4")
    if build_if_missing and (not manifest.get("exists") or manifest.get("status") == "not_built"):
        manifest = build_feature_store(version="v4")
    cross_market, event, incremental = _split_incremental_fields(manifest if isinstance(manifest, Mapping) else {})
    excluded, exclusion_reasons = _excluded_reasons(manifest if isinstance(manifest, Mapping) else {})
    status = "ready" if incremental else "blocked"
    payload = {
        "status": status,
        "candidate_version": "v4",
        "dataset_version": "v4",
        "feature_store_version": "v4",
        "feature_set": V4_FEATURE_SET,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "incremental_feature_cols": incremental,
        "cross_market_feature_cols": cross_market,
        "event_feature_cols": event,
        "excluded_fields": excluded,
        "exclusion_reasons": exclusion_reasons,
        "feature_store_path": manifest.get("feature_store_path") if isinstance(manifest, Mapping) else "",
        "feature_store_manifest_path": manifest.get("manifest_path") if isinstance(manifest, Mapping) else "",
        "reason_zh": "" if incremental else BLOCKED_REASON_ZH,
        "sample_data_used": False,
        "baseline_used": False,
        "active_model_written": False,
        "customer_prediction_generated": False,
        "promotion_gate_lowered": False,
    }
    _write_json(_readiness_path(), payload)
    return sanitize_for_json(payload)


def build_feature_store_v4() -> dict[str, Any]:
    manifest = build_feature_store(version="v4")
    readiness = check_feature_store_v4_readiness(build_if_missing=False)
    if readiness.get("status") == "blocked":
        return sanitize_for_json({**readiness, "feature_store_manifest": manifest})
    payload = {
        **readiness,
        "status": "success",
        "feature_store_manifest": manifest,
        "message_zh": "Feature Store v4 已构建，且存在真实新增 cross-market/event 字段。本步骤未训练模型、未生成预测、未发布 active。",
    }
    _write_json(_readiness_path(), payload)
    return sanitize_for_json(payload)


def build_training_dataset_v4(*, horizons: Iterable[int] = (1, 3, 5, 10, 20), min_feature_coverage: float = 0.7) -> dict[str, Any]:
    readiness = check_feature_store_v4_readiness()
    if readiness.get("status") == "blocked":
        return sanitize_for_json(
            {
                **readiness,
                "status": "blocked",
                "manifest_path": str(_output_dir() / "training_dataset_manifest_v4.json"),
                "message_zh": BLOCKED_REASON_ZH,
            }
        )
    dataset = build_training_dataset(
        horizons=horizons,
        min_feature_coverage=min_feature_coverage,
        dataset_version="v4",
        feature_store_version="v4",
        feature_set=V4_FEATURE_SET,
    )
    dataset["incremental_feature_cols"] = list(readiness.get("incremental_feature_cols") or [])
    dataset["cross_market_feature_cols"] = list(readiness.get("cross_market_feature_cols") or [])
    dataset["event_feature_cols"] = list(readiness.get("event_feature_cols") or [])
    dataset["excluded_fields"] = list(readiness.get("excluded_fields") or [])
    dataset["exclusion_reasons"] = dict(readiness.get("exclusion_reasons") or {})
    dataset["no_lookahead_pass"] = bool(dataset.get("leakage_check_pass"))
    dataset["sample_data_used"] = False
    dataset["baseline_used"] = False
    dataset["active_model_written"] = False
    dataset["customer_prediction_generated"] = False
    manifest_path = Path(str(dataset.get("manifest_path") or (_output_dir() / "training_dataset_manifest_v4.json")))
    _write_json(manifest_path, dataset)
    return sanitize_for_json(dataset)


def run_candidate_v4_research(*, horizons: Iterable[str] = DEFAULT_HORIZONS) -> dict[str, Any]:
    horizon_list = tuple(str(item) for item in horizons)
    readiness = check_feature_store_v4_readiness()
    if readiness.get("status") == "blocked":
        return sanitize_for_json(
            {
                **readiness,
                "status": "blocked",
                "horizons": horizon_list,
                "message_zh": BLOCKED_REASON_ZH,
                "candidate": {"status": "not_run", "reason_zh": BLOCKED_REASON_ZH},
                "research_backtest": {"status": "not_run"},
                "strategy_optimization": {"status": "not_run"},
                "institutional_validation": {"status": "not_run"},
                "promotion_dry_run": {"status": "not_run"},
                "active_updated": False,
                "customer_prediction_generated": False,
                "baseline_used": False,
                "sample_data_used": False,
            }
        )

    feature_store = get_feature_store_status(version="v4")
    if not feature_store.get("exists"):
        feature_store = build_feature_store(version="v4")

    dataset = get_training_dataset_status(dataset_version="v4")
    if not dataset.get("exists"):
        dataset = build_training_dataset_v4()

    candidate = run_candidate_training(
        horizons=horizon_list,
        candidate_version="v4",
        dataset_version="v4",
        feature_set=V4_FEATURE_SET,
        label_variants=V4_LABEL_VARIANTS,
        models=V4_MODELS,
        calibration=V4_CALIBRATION,
        no_trade_filters=V4_NO_TRADE_FILTERS,
    )
    oof_integrity = get_oof_integrity_report(candidate_version="v4", dataset_version="v4")
    institutional_validation = run_institutional_validation(candidate_version="v4", dry_run=True)
    promotion_dry_run = promote_candidate(candidate_version="v4", dry_run=True)
    backtest = run_research_backtest(candidate_version="v4", horizons=horizon_list)
    optimization = optimize_research_strategy(candidate_version="v4", horizons=horizon_list)
    archive = archive_research_run(
        candidate_version="v4",
        extra_payload={
            "feature_store_status": feature_store.get("status"),
            "training_dataset_status": dataset.get("status"),
            "candidate_status": candidate.get("status"),
            "incremental_feature_cols": readiness.get("incremental_feature_cols"),
            "institutional_validation_status": institutional_validation.get("status"),
            "promotion_dry_run_status": promotion_dry_run.get("status"),
        },
    )
    return sanitize_for_json(
        {
            "status": "success" if candidate.get("status") == "success" else "failed",
            "candidate_version": "v4",
            "dataset_version": "v4",
            "feature_store_version": "v4",
            "feature_set": V4_FEATURE_SET,
            "horizons": horizon_list,
            "incremental_feature_cols": readiness.get("incremental_feature_cols"),
            "cross_market_feature_cols": readiness.get("cross_market_feature_cols"),
            "event_feature_cols": readiness.get("event_feature_cols"),
            "candidate": candidate,
            "oof_integrity": oof_integrity,
            "institutional_validation": institutional_validation,
            "promotion_dry_run": promotion_dry_run,
            "research_backtest": backtest,
            "strategy_optimization": optimization,
            "artifact_dir": archive.get("artifact_dir"),
            "artifact_run_id": archive.get("run_id"),
            "message_zh": "candidate_v4 研究流程已完成；未发布 active，未生成客户预测，未降低 promotion gate。",
            "active_updated": False,
            "customer_prediction_generated": False,
            "baseline_used": False,
            "sample_data_used": False,
        }
    )


def get_feature_store_v4_readiness() -> dict[str, Any]:
    payload = _read_json(_readiness_path())
    if isinstance(payload, Mapping):
        return sanitize_for_json(dict(payload))
    return check_feature_store_v4_readiness(build_if_missing=False)
