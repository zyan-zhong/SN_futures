from __future__ import annotations

from pathlib import Path


def test_refresh_buttons_disable_during_task_start_and_use_short_copy() -> None:
    refresh_panel = Path("frontend/src/components/data/RefreshTaskPanel.tsx").read_text(encoding="utf-8")
    task_bar = Path("frontend/src/components/task/GlobalTaskBar.tsx").read_text(encoding="utf-8")

    assert "disabled={Boolean(running)}" in refresh_panel
    assert "刷新中" in refresh_panel
    assert "Task Notification Center" in task_bar
    assert "details" in task_bar
    assert "长任务在后台执行" not in task_bar


def test_no_long_json_or_repeated_disclaimer_in_simple_mode_components() -> None:
    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    sidebar = Path("frontend/src/components/layout/SimpleSidebar.tsx").read_text(encoding="utf-8")

    assert "JSON.stringify" not in app
    assert "JSON.stringify" not in sidebar
    assert sidebar.count("不构成投资建议") == 0
