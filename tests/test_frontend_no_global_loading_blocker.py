from __future__ import annotations

from pathlib import Path


def test_app_snapshot_loading_only_blocks_dashboard_not_other_pages() -> None:
    app = Path("frontend/src/App.tsx").read_text(encoding="utf-8")

    assert 'page === "dashboard"' in app
    assert "LoadingState" in app
    assert "<MarketMonitorPage />" in app
    assert "<ResearchLabPage />" in app


def test_polling_uses_backoff_and_pauses_when_page_hidden() -> None:
    hook = Path("frontend/src/hooks/usePolling.ts").read_text(encoding="utf-8")

    assert "document.hidden" in hook
    assert "Math.min" in hook
    assert "backoff" in hook
    assert "visibilitychange" in hook
