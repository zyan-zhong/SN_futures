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


def test_installed_smoke_forces_cleanup_after_shutdown_port_release() -> None:
    script = Path("packaging/smoke_installed.ps1").read_text(encoding="utf-8")

    assert "function Stop-SmokeProcessIfRunning" in script
    assert "installed process still running after shutdown API; forcing cleanup" in script
    assert 'Assert-True ($process.HasExited) "installed process exited after shutdown API"' not in script
    cleanup_call = "Stop-SmokeProcessIfRunning -Process $process"
    orphan_assertion_call = "\n  Assert-NoSNInsightOrphanProcess"
    assert cleanup_call in script
    assert orphan_assertion_call in script
    assert script.index("Assert-PortReleased -Port $port") < script.index(cleanup_call)
    assert script.index(cleanup_call) < script.index(orphan_assertion_call)


def test_settings_page_exposes_background_shutdown_controls() -> None:
    page = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
    api = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")

    assert "停止后台服务" in page
    assert "关闭终端时自动停止后台服务" in page
    assert "getProcessStatus" in api
    assert "shutdownBackend" in api
