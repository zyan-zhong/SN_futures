from __future__ import annotations

from typing import Any, Iterable

from ..api.json_utils import sanitize_for_json
from .feature_store_service import build_feature_store, get_feature_store_status
from .institutional_validation_service import run_institutional_validation
from .model_promotion_service import promote_candidate
from .oof_integrity_service import get_oof_integrity_report
from .research_artifact_service import archive_research_run
from .research_backtest_service import run_research_backtest
from .research_strategy_optimizer import optimize_research_strategy
from .training_dataset_service import build_training_dataset, get_training_dataset_status
from .walk_forward_training_service import run_candidate_training


DEFAULT_HORIZONS = ("1d", "3d", "5d", "10d", "20d")
V3_FEATURE_SET = "ohlcv_technical_regime_cross_market_event"
V3_LABEL_VARIANTS = ("direction_thresholded", "volatility_adjusted_direction", "triple_barrier_atr")
V3_MODELS = ("lightgbm_gbdt", "hist_gradient_boosting", "extra_trees", "random_forest")
V3_CALIBRATION = ("sigmoid", "isotonic")
V3_NO_TRADE_FILTERS = ("low_confidence", "low_edge", "high_volatility", "event_shock", "high_vol_drawdown_guard")


def run_candidate_v3_research(*, horizons: Iterable[str] = DEFAULT_HORIZONS) -> dict[str, Any]:
    horizon_list = tuple(str(item) for item in horizons)
    feature_store = get_feature_store_status(version="v3")
    if not feature_store.get("exists"):
        feature_store = build_feature_store(version="v3")

    dataset = get_training_dataset_status(dataset_version="v3")
    if not dataset.get("exists"):
        dataset = build_training_dataset(
            dataset_version="v3",
            feature_store_version="v3",
            feature_set=V3_FEATURE_SET,
        )

    candidate = run_candidate_training(
        horizons=horizon_list,
        candidate_version="v3",
        dataset_version="v3",
        feature_set=V3_FEATURE_SET,
        label_variants=V3_LABEL_VARIANTS,
        models=V3_MODELS,
        calibration=V3_CALIBRATION,
        no_trade_filters=V3_NO_TRADE_FILTERS,
    )
    oof_integrity = get_oof_integrity_report(candidate_version="v3", dataset_version="v3")
    institutional_validation = run_institutional_validation(candidate_version="v3", dry_run=True)
    promotion_dry_run = promote_candidate(candidate_version="v3", dry_run=True)
    backtest = run_research_backtest(candidate_version="v3", horizons=horizon_list)
    optimization = optimize_research_strategy(candidate_version="v3", horizons=horizon_list)
    archive = archive_research_run(
        candidate_version="v3",
        extra_payload={
            "feature_store_status": feature_store.get("status"),
            "training_dataset_status": dataset.get("status"),
            "candidate_status": candidate.get("status"),
            "institutional_validation_status": institutional_validation.get("status"),
            "promotion_dry_run_status": promotion_dry_run.get("status"),
        },
    )
    status = "success" if candidate.get("status") == "success" else "failed"
    return sanitize_for_json(
        {
            "status": status,
            "candidate_version": "v3",
            "dataset_version": "v3",
            "feature_store_version": "v3",
            "feature_set": V3_FEATURE_SET,
            "horizons": horizon_list,
            "candidate": candidate,
            "oof_integrity": oof_integrity,
            "institutional_validation": institutional_validation,
            "promotion_dry_run": promotion_dry_run,
            "research_backtest": backtest,
            "strategy_optimization": optimization,
            "artifact_dir": archive.get("artifact_dir"),
            "artifact_run_id": archive.get("run_id"),
            "message_zh": "candidate_v3 研究流程已完成；未发布 active，未生成客户预测。",
            "active_updated": False,
            "customer_prediction_generated": False,
            "baseline_used": False,
            "sample_data_used": False,
        }
    )

