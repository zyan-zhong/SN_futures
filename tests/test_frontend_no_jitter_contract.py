from __future__ import annotations

from pathlib import Path


def test_global_task_bar_is_fixed_and_does_not_reflow_workspace() -> None:
    component = Path("frontend/src/components/task/GlobalTaskBar.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/styles/globals.css").read_text(encoding="utf-8")

    assert "global-task-bar" in component
    assert ".global-task-bar" in css
    assert "position: fixed" in css
    assert "stale-while-refreshing" in component


def test_pages_keep_existing_data_while_refreshing() -> None:
    market = Path("frontend/src/pages/MarketMonitorPage.tsx").read_text(encoding="utf-8")
    dashboard = Path("frontend/src/pages/DashboardPage.tsx").read_text(encoding="utf-8")

    assert "isRefreshing" in market
    assert "disabled={isRefreshing}" in market
    assert "刷新中" in market
    assert "simple-dashboard-grid" in dashboard
    assert "dashboard-extra-detail" in dashboard

