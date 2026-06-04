from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_data_status_page_exposes_tushare_auxiliary_subinterfaces() -> None:
    content = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

    for expected in (
        "tushare_subinterfaces",
        "tushare_contracts",
        "tushare_daily",
        "tushare_warehouse",
        "tushare_settlement",
        "tushare_holding",
        "selected_params",
        "last_success_time",
    ):
        assert expected in content


def test_factor_page_displays_feature_store_v6_auxiliary_fields() -> None:
    content = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")

    for expected in (
        'getFeatureStoreStatus("v6")',
        'buildFeatureStore({ version: "v6" })',
        "warehouse_receipt_delta_1w",
        "trading_fee",
        "long_margin_rate",
        "member_net_position",
        "failed_subinterfaces",
    ):
        assert expected in content


def test_factor_and_training_pages_display_feature_store_v7_cost_positioning() -> None:
    factor_page = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")
    training_page = (ROOT / "frontend" / "src" / "pages" / "TrainingDataPage.tsx").read_text(encoding="utf-8")
    types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

    for expected in (
        'getFeatureStoreStatus("v7")',
        'buildFeatureStore({ version: "v7" })',
        "v7 cost features",
        "v7 positioning features",
        "v7 sparse policy",
        "sparse_feature_policy",
    ):
        assert expected in factor_page
    for expected in (
        '"v7"',
        "institutional_tushare_cost_positioning",
        "cost_features",
        "positioning_features",
        "no_lookahead_pass",
    ):
        assert expected in training_page
    for expected in ("cost_features", "positioning_features", "sparse_feature_policy", "mock_data_used"):
        assert expected in types
