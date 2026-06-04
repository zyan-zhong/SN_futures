from __future__ import annotations

from pathlib import Path


def test_installed_smoke_uses_shutdown_api_before_force_kill() -> None:
    script = Path("packaging/smoke_installed.ps1").read_text(encoding="utf-8")

    assert "/api/terminal/system/process-status" in script
    assert "/api/terminal/system/shutdown" in script
    assert "Assert-PortReleased" in script
    assert "Assert-NoSNInsightOrphanProcess" in script
    assert "Stop-Process -Id $process.Id -Force" in script
    assert script.index("/api/terminal/system/shutdown") < script.index("Stop-Process -Id $process.Id -Force")


def test_settings_page_exposes_background_shutdown_controls() -> None:
    page = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    api = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")

    assert "停止后台服务" in page
    assert "关闭终端时自动停止后台服务" in page
    assert "getProcessStatus" in api
    assert "shutdownBackend" in api
