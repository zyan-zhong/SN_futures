from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PANEL = ROOT / "frontend" / "src" / "components" / "data" / "DataSourceStatusPanel.tsx"
TYPES = ROOT / "frontend" / "src" / "api" / "types.ts"


def test_data_source_panel_uses_freshness_label() -> None:
    text = PANEL.read_text(encoding="utf-8")
    assert "freshness_label" in text
    assert "row_count" in text
    assert "next_actions_zh" in text
    assert "未配置" in text
    assert "使用缓存" in text
    assert "未启用" in text


def test_data_source_types_include_provider_status_schema() -> None:
    text = TYPES.read_text(encoding="utf-8")
    for field in (
        "configured",
        "attempted",
        "freshness_label",
        "row_count",
        "next_actions_zh",
        "next_expected_update",
    ):
        assert field in text


def test_data_source_panel_does_not_expose_key_values() -> None:
    text = PANEL.read_text(encoding="utf-8").lower()
    assert "api key" in text or "key" in text
    assert "localstorage" not in text
    assert "authorization" not in text
    assert "bearer" not in text
