from __future__ import annotations

from pathlib import Path


def test_app_defaults_to_simple_mode_and_can_switch_to_professional_mode() -> None:
    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    sidebar = Path("frontend/src/components/layout/SimpleSidebar.tsx").read_text(encoding="utf-8")

    assert 'useLocalSetting<"simple" | "professional">("uiMode", "simple")' in app
    assert "simple-nav" in sidebar
    assert "professional-nav" in sidebar
    assert 'data-testid="ui-mode-toggle"' in sidebar
    for label in [
        "Terminal Overview",
        "Prediction Workspace",
        "Data Onboarding",
        "Candidate Research",
        "Research Governance",
        "Settings",
    ]:
        assert label in sidebar


def test_settings_exposes_default_startup_mode_without_long_copy() -> None:
    settings = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")

    assert "默认启动模式" in settings
    assert "简洁" in settings
    assert "专业" in settings
    assert "setUIMode" in settings


def test_public_terminal_default_shell_does_not_mount_legacy_terminal_pollers() -> None:
    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    shell = Path("frontend/src/components/layout/AppShell.tsx").read_text(encoding="utf-8")
    snapshot_hook = Path("frontend/src/hooks/useTerminalSnapshot.ts").read_text(encoding="utf-8")
    first_run_hook = Path("frontend/src/hooks/useFirstRun.ts").read_text(encoding="utf-8")

    assert 'const legacyTerminalAdaptersEnabled = devConsoleEnabled && effectiveUIMode === "professional"' in app
    assert "useTerminalSnapshot(30000, legacyTerminalAdaptersEnabled)" in app
    assert "useFirstRun(legacyTerminalAdaptersEnabled)" in app
    assert "showGlobalTaskBar={legacyTerminalAdaptersEnabled}" in app
    assert "showGlobalTaskBar" in shell
    assert "{showGlobalTaskBar ? <GlobalTaskBar /> : null}" in shell
    assert "useTerminalSnapshot(intervalMs = 30000, enabled = true)" in snapshot_hook
    assert "usePolling<TerminalSnapshot>(loader, intervalMs, enabled)" in snapshot_hook
    assert "useFirstRun(enabled = true)" in first_run_hook
    assert "if (!enabled)" in first_run_hook
