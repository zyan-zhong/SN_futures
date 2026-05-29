from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_terminal_client_exposes_feature_store_api() -> None:
    source = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
    assert "buildFeatureStore" in source
    assert "getFeatureStoreStatus" in source
    assert "/api/terminal/feature-store/build" in source
    assert "/api/terminal/feature-store/status" in source


def test_factor_page_exposes_feature_store_v3_contract() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")
    assert "Feature Store v3" in source
    assert "一键构建 Feature Store" in source
    assert "不生成预测" in source
    assert "usable_fields" in source
    assert "excluded_fields" in source
