from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_settings_page_displays_tushare_configured_source_masked_and_test_button() -> None:
    content = (ROOT / "frontend" / "src" / "pages" / "SettingsPage.tsx").read_text(encoding="utf-8")

    assert "tushare_configured" in content
    assert "tushare_masked" in content
    assert "tushare_source" in content
    assert "测试 Tushare" in content
    assert "SN_TUSHARE_TOKEN" in content


def test_frontend_types_do_not_expose_tushare_secret_value() -> None:
    types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

    assert "tushare_masked" in types
    assert "tushare_source" in types
    assert "SN_TUSHARE_TOKEN" not in types
