from __future__ import annotations

from pathlib import Path


def test_frontend_has_active_absence_api_helper_and_type() -> None:
    terminal = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
    types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")

    assert "getActiveAbsenceDiagnostics" in terminal
    assert "/api/terminal/models/active-absence-diagnostics" in terminal
    assert "ActiveAbsenceDiagnosticsPayload" in types
    assert "candidate_v6_plan" in types


def test_prediction_and_research_pages_explain_no_active_without_fake_prediction() -> None:
    prediction_page = Path("frontend/src/pages/PredictionPage.tsx").read_text(encoding="utf-8")
    research_page = Path("frontend/src/pages/ResearchLabPage.tsx").read_text(encoding="utf-8")

    combined = prediction_page + "\n" + research_page
    assert "active-absence" in combined or "ActiveAbsence" in combined
    assert "candidate_v6" in combined
    assert "Why no active model" in prediction_page
    assert "Why no active model" in research_page
    assert "activeAbsence?.root_causes" in research_page
    assert "fake prediction" not in combined.lower()
    assert "建议买入" not in combined
    assert "建议卖出" not in combined
