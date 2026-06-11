from __future__ import annotations


PUBLIC_PREDICTION_CORE_SCHEMA_VERSION = "public-prediction-core-readiness-v1"

DOWNSTREAM_FALSE_FLAGS = {
    "training_invoked": False,
    "prediction_generated": False,
    "backtest_invoked": False,
    "feature_store_written": False,
    "production_cache_written": False,
    "customer_prediction_generated": False,
    "candidate_training_invoked": False,
    "candidate_promotion_invoked": False,
}

FORBIDDEN_PREDICTION_OUTPUT_KEYS = {
    "prediction_card",
    "prediction_value",
    "forecast_price",
    "forecast_range",
    "price_range",
    "prob_up",
    "prob_down",
    "predicted_direction",
    "direction_prediction",
    "target_price",
}

DIRTY_FLAGS = {
    "sample",
    "sample_mode",
    "sample_data_used",
    "fake",
    "fake_data_used",
    "demo",
    "demo_data_used",
    "baseline",
    "baseline_used",
    "mock_data_used",
}
