from __future__ import annotations

from pathlib import Path


def test_task_monitor_is_fixed_and_does_not_reflow_pages() -> None:
    css = Path("frontend/src/styles/globals.css").read_text(encoding="utf-8")
    panel = Path("frontend/src/components/common/TaskMonitorPanel.tsx").read_text(encoding="utf-8")

    assert ".task-monitor-panel" in css
    assert "position: fixed" in css
    assert "getRecentTerminalTasks" in panel
    assert "getTerminalTaskStatus" in panel


def test_refresh_buttons_have_pending_or_disabled_state() -> None:
    pages = "\n".join(path.read_text(encoding="utf-8") for path in Path("frontend/src/pages").glob("*.tsx"))

    assert "disabled={loading}" in pages or "disabled={researchLoading}" in pages
    assert "stale" in pages.lower() or "cache" in pages.lower() or "缓存" in pages
    assert "全局 loading" not in pages
