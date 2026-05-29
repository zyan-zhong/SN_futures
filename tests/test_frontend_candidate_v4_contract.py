from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def test_frontend_exposes_candidate_v4_research_api_contract() -> None:
    api = (FRONTEND / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
    assert "runCandidateV4Research" in api
    assert "/api/terminal/research/run-candidate-v4" in api
    assert "version?: string" in api


def test_research_lab_shows_candidate_v4_blocking_reason_and_boundaries() -> None:
    page = (FRONTEND / "src" / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")
    assert "candidate_v4 readiness and research" in page
    assert "real cross-market or event incremental fields" in page
    assert "does not write active_model.json" in page
    assert "does not generate customer predictions" in page
    assert "v1/v2/v3/v4 comparison" in page


def test_backtest_page_supports_v3_v4_research_selector() -> None:
    page = (FRONTEND / "src" / "pages" / "BacktestPage.tsx").read_text(encoding="utf-8")
    assert "research backtest selector" in page
    assert "candidate_v3" in page
    assert "candidate_v4" in page
    assert "researchVersion" in page
