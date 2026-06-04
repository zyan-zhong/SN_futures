from __future__ import annotations

from typing import Any, Iterable

from ..api.json_utils import sanitize_for_json
from .feature_store_v5_service import V5_FEATURE_SET, build_feature_store_v5
from .institutional_validation_service import run_institutional_validation
from .model_promotion_service import promote_candidate
from .multi_objective_research_optimizer import optimize_multi_objective_research_strategy
from .oof_integrity_service import get_oof_integrity_report
from .research_artifact_service import archive_research_run
from .research_backtest_service import run_research_backtest
from .training_dataset_service import build_training_dataset, get_training_dataset_status
from .walk_forward_training_service import run_candidate_training


DEFAULT_HORIZONS = ("1d", "3d", "5d", "10d", "20d")
V5_LABEL_VARIANTS = ("direction_thresholded", "volatility_adjusted_direction", "triple_barrier_atr")
V5_MODELS = ("lightgbm_gbdt", "hist_gradient_boosting", "extra_trees", "random_forest")
V5_CALIBRATION = ("sigmoid", "isotonic")
V5_NO_TRADE_FILTERS = (
    "low_confidence",
    "low_edge",
    "high_volatility",
    "event_shock",
    "rate_limit_stale_data_guard",
    "managed_data_quality_guard",
)


def run_candidate_v5_research(*, horizons: Iterable[str] = DEFAULT_HORIZONS) -> dict[str, Any]:
    horizon_list = tuple(str(item) for item in horizons)
    feature_store = build_feature_store_v5()

    dataset = get_training_dataset_status(dataset_version="v5")
    if not dataset.get("exists"):
        dataset = build_training_dataset(
            dataset_version="v5",
            feature_store_version="v5",
            feature_set=V5_FEATURE_SET,
        )

    candidate = run_candidate_training(
        horizons=horizon_list,
        candidate_version="v5",
        dataset_version="v5",
        feature_set=V5_FEATURE_SET,
        label_variants=V5_LABEL_VARIANTS,
        models=V5_MODELS,
        calibration=V5_CALIBRATION,
        no_trade_filters=V5_NO_TRADE_FILTERS,
    )
    oof_integrity = get_oof_integrity_report(candidate_version="v5", dataset_version="v5")
    backtest = run_research_backtest(candidate_version="v5", horizons=horizon_list)
    optimization = optimize_multi_objective_research_strategy(candidate_version="v5", horizons=horizon_list)
    institutional_validation = run_institutional_validation(candidate_version="v5", dry_run=True)
    promotion_dry_run = promote_candidate(candidate_version="v5", dry_run=True)
    archive = archive_research_run(
        candidate_version="v5",
        extra_payload={
            "feature_store_status": feature_store.get("status"),
            "training_dataset_status": dataset.get("status"),
            "candidate_status": candidate.get("status"),
            "multi_objective_status": optimization.get("status"),
            "institutional_validation_status": institutional_validation.get("status"),
            "promotion_dry_run_status": promotion_dry_run.get("status"),
        },
    )

    return sanitize_for_json(
        {
            "status": "success" if candidate.get("status") == "success" else "failed",
            "candidate_version": "v5",
            "dataset_version": "v5",
            "feature_store_version": "v5",
            "feature_set": V5_FEATURE_SET,
            "horizons": horizon_list,
            "candidate": candidate,
            "oof_integrity": oof_integrity,
            "research_backtest": backtest,
            "multi_objective_optimization": optimization,
            "institutional_validation": institutional_validation,
            "promotion_dry_run": promotion_dry_run,
            "artifact_dir": archive.get("artifact_dir"),
            "artifact_run_id": archive.get("run_id"),
            "promotion_readiness": optimization.get("promotion_readiness", "research_only"),
            "message_zh": "candidate_v5 research pipeline completed. No active model was published and no customer prediction was generated.",
            "active_updated": False,
            "customer_prediction_generated": False,
            "baseline_used": False,
            "sample_data_used": False,
            "promotion_gate_lowered": False,
        }
    )
