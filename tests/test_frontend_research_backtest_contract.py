from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _api_client_surface() -> str:
    api_dir = ROOT / "frontend" / "src" / "api"
    return "\n".join(
        (api_dir / name).read_text(encoding="utf-8")
        for name in ("terminal.ts", "backtest.ts")
    )


def test_frontend_exposes_research_backtest_api_contract() -> None:
    api = _api_client_surface()
    assert "runCandidateV3Research" in api
    assert "runResearchBacktest" in api
    assert "getAuditableResearchBacktest" in api
    assert "/api/terminal/backtest/auditable" in api
    assert "getResearchBacktestReport" in api
    assert "getResearchEquityCurve" in api
    assert "getResearchArtifacts" in api
    assert "optimizeResearchStrategy" in api


def test_backtest_page_marks_research_backtest_as_non_live_prediction() -> None:
    page = (ROOT / "frontend" / "src" / "pages" / "BacktestPage.tsx").read_text(encoding="utf-8")
    assert "研究型收益曲线" in page
    assert "研究回测，不代表 live active 预测，不构成投资建议。" in page
    assert "不生成客户预测" in page


def test_research_lab_shows_candidate_v3_artifacts_and_comparison() -> None:
    page = (ROOT / "frontend" / "src" / "pages" / "ResearchLabPage.tsx").read_text(encoding="utf-8")
    assert "candidate_v3" in page
    assert "strategy optimization" in page
    assert "artifacts 下载" in page
    assert "v1/v2/v3 对比" in page
    assert "不发布 active" in page
