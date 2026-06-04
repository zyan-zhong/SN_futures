from __future__ import annotations

from pathlib import Path


def test_app_defaults_to_simple_mode_and_can_switch_to_professional_mode() -> None:
    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    sidebar = Path("frontend/src/components/layout/SimpleSidebar.tsx").read_text(encoding="utf-8")

    assert 'useLocalSetting<"simple" | "professional">("uiMode", "simple")' in app
    assert "simple-nav" in sidebar
    assert "professional-nav" in sidebar
    assert 'data-testid="ui-mode-toggle"' in sidebar
    for label in ["总览", "行情", "数据", "研究", "报告", "设置"]:
        assert label in sidebar


def test_settings_exposes_default_startup_mode_without_long_copy() -> None:
    settings = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")

    assert "默认启动模式" in settings
    assert "简洁" in settings
    assert "专业" in settings
    assert "setUIMode" in settings
