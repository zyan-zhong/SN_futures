from __future__ import annotations

from pathlib import Path


def test_heavy_pages_are_lazy_loaded_behind_suspense() -> None:
    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert "lazy(" in app
    assert "Suspense" in app
    for page in (
        "BacktestPage",
        "FactorPage",
        "ModelGovernancePage",
        "ResearchLabPage",
        "ReportsPage",
        "TrainingDataPage",
    ):
        assert f"const {page} = lazy(" in app


def test_dashboard_remains_eager_and_no_global_loading_gate_blocks_other_pages() -> None:
    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'from "./pages/DashboardPage"' in app
    assert "page === \"dashboard\"" in app
    assert "return <LoadingState" not in app.split("switch (page)")[0] or "page === \"dashboard\"" in app.split("switch (page)")[0]
