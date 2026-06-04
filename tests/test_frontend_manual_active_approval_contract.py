from __future__ import annotations

from pathlib import Path


def test_frontend_exposes_manual_active_approval_controls() -> None:
    terminal_api = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
    types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")
    page = Path("frontend/src/pages/ResearchLabPage.tsx").read_text(encoding="utf-8")
    backend = Path("src/sn_futures/api/terminal_api.py").read_text(encoding="utf-8")

    assert "approveActiveModel" in terminal_api
    assert '"/api/terminal/models/approve-active"' in terminal_api
    assert "ActiveReleaseApprovalPayload" in types
    assert "人工审批 active 发布" in page
    assert "我确认仅作为研究预测，不构成投资建议" in page
    assert "不会接实盘" in page
    assert "/api/terminal/models/approve-active" in backend
