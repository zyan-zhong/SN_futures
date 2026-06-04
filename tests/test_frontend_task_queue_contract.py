from __future__ import annotations

from pathlib import Path


def test_frontend_has_task_queue_api_helpers() -> None:
    terminal = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")

    assert "startTerminalTask" in terminal
    assert "getTerminalTaskStatus" in terminal
    assert "getRecentTerminalTasks" in terminal
    assert "cancelTerminalTask" in terminal
    assert "/api/terminal/tasks/start" in terminal
    assert "/api/terminal/tasks/status" in terminal


def test_task_monitor_panel_polls_status_and_can_cancel() -> None:
    panel = Path("frontend/src/components/common/TaskMonitorPanel.tsx").read_text(encoding="utf-8")

    assert "TaskMonitorPanel" in panel
    assert "getTerminalTaskStatus" in panel
    assert "getRecentTerminalTasks" in panel
    assert "cancelTerminalTask" in panel
    assert "setInterval" in panel or "usePolling" in panel
    assert "取消" in panel
