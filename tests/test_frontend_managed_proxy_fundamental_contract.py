from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_frontend_exposes_managed_fundamentals_and_v10_status() -> None:
    data_status = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")
    factor_page = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")
    terminal_api = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")

    for expected in (
        "managed fundamentals",
        "shfe_warehouse_receipt",
        "shfe_inventory",
        "spot_futures_basis",
        "lme_tin_close",
        "lme_inventory",
        "no_fake_data",
    ):
        assert expected in data_status or expected in factor_page
    assert 'getFeatureStoreStatus("v10")' in factor_page
    assert 'buildFeatureStore({ version: "v10" })' in factor_page
    assert "Feature Store v10" in factor_page
    assert "version=feature_store_v10" not in terminal_api
