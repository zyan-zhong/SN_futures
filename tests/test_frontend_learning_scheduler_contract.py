from __future__ import annotations

from pathlib import Path


def test_learning_scheduler_api_contract_is_exposed_to_frontend() -> None:
    terminal_api = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
    types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")

    assert "LearningSchedulerStatus" in types
    assert "getLearningSchedulerStatus" in terminal_api
    assert '"/api/terminal/learning-scheduler/status"' in terminal_api
    assert '"/api/terminal/learning-scheduler/run"' in terminal_api
    assert '"/api/terminal/learning-scheduler/pause"' in terminal_api
    assert '"/api/terminal/learning-scheduler/resume"' in terminal_api


def test_research_lab_shows_learning_scheduler_controls_and_no_auto_active_copy() -> None:
    page = Path("frontend/src/pages/ResearchLabPage.tsx").read_text(encoding="utf-8")

    assert "自学习调度器" in page
    assert "手动运行" in page
    assert "暂停" in page
    assert "恢复" in page
    assert "人工审批" in page
    assert "不会自动发布 active" in page
