from __future__ import annotations

from pathlib import Path


FRONTEND = Path("frontend/src")


def test_data_status_page_exposes_data_consistency_report_and_reload_action() -> None:
    source = (FRONTEND / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

    assert "数据一致性报告" in source
    assert "当前最新数据时间" in source
    assert "页面数据时间" in source
    assert "一键重新加载" in source
    assert "getDataConsistencyReport" in source
    assert "demo prediction" not in source.lower()


def test_frontend_api_client_has_data_consistency_endpoint() -> None:
    api = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")

    assert "getDataConsistencyReport" in api
    assert "/api/terminal/data-consistency-report" in api
