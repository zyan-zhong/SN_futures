from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_data_status_page_mentions_alpha_rate_limit_cache_and_cooldown() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

    assert "rate_limited" in source
    assert "using_cache_rate_limited" in source
    assert "cooldown_until" in source
    assert "last_success_time" in source


def test_factor_page_mentions_cross_market_alignment_and_cache_status() -> None:
    source = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")

    assert "cross_market_diagnostics" in source
    assert "from_cache" in source
    assert "stale" in source
