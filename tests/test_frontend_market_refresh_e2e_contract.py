from __future__ import annotations

from pathlib import Path


def test_playwright_market_refresh_validation_exists() -> None:
    text = Path("frontend/e2e/terminal.spec.ts").read_text(encoding="utf-8")

    assert "/api/terminal/refresh/market" in text
    assert "/api/terminal/charts/price-history" in text
    assert "/api/terminal/providers/status-detail" in text
    assert "market-refresh-validation.png" in text


def test_frontend_market_refresh_e2e_forbids_baseline_wording() -> None:
    text = Path("frontend/e2e/terminal.spec.ts").read_text(encoding="utf-8").lower()

    assert "baseline forecast" not in text
    assert "baseline backtest" not in text
    assert "基线预测" not in text
    assert "基线回测" not in text

