from __future__ import annotations

from pathlib import Path


def test_all_primary_pages_have_api_or_empty_state_contract() -> None:
    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")
    page_dir = Path("frontend/src/pages")
    required = [
        "DashboardPage",
        "MarketMonitorPage",
        "EventPage",
        "FactorPage",
        "TrainingDataPage",
        "ResearchLabPage",
        "BacktestPage",
        "PredictionPage",
        "ReportsPage",
        "SettingsPage",
    ]
    for page in required:
        assert page in app

    combined = "\n".join(path.read_text(encoding="utf-8") for path in page_dir.glob("*.tsx"))
    assert "EmptyState" in combined
    assert "ErrorState" in combined
    for visible_bad_literal in [">undefined<", ">null<", ">NaN<", '"undefined"', "'undefined'"]:
        assert visible_bad_literal not in combined
    assert "fake prediction" not in combined.lower()
    assert "保证盈利" not in combined
