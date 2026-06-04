from __future__ import annotations

from pathlib import Path


def test_price_chart_uses_price_history_dates_prices_and_key_level_marklines() -> None:
    chart = Path("frontend/src/components/charts/PriceChart.tsx").read_text(encoding="utf-8")

    assert "historyPoints.map((item) => item.time" in chart
    assert "toFiniteNumber(item.close)" in chart
    assert "toFiniteNumber(item.high)" in chart
    assert "toFiniteNumber(item.low)" in chart
    assert "markLine" in chart
    assert "支撑" in chart
    assert "压力" in chart


def test_research_backtest_visuals_are_labeled_research_only() -> None:
    backtest = Path("frontend/src/pages/BacktestPage.tsx").read_text(encoding="utf-8")
    equity = Path("frontend/src/components/charts/EquityCurveChart.tsx").read_text(encoding="utf-8")
    drawdown = Path("frontend/src/components/charts/DrawdownChart.tsx").read_text(encoding="utf-8")

    assert "研究回测" in backtest or "research backtest" in backtest.lower()
    assert "active live" not in backtest.lower()
    assert "equity_curve" in equity or "equity" in equity.lower()
    assert "drawdown" in drawdown.lower()
    assert "percent" in drawdown.lower() or "%" in drawdown


def test_factor_training_event_pages_reference_manifest_or_filtered_inputs() -> None:
    factor = Path("frontend/src/pages/FactorPage.tsx").read_text(encoding="utf-8")
    training = Path("frontend/src/pages/TrainingDataPage.tsx").read_text(encoding="utf-8")
    events = Path("frontend/src/pages/EventPage.tsx").read_text(encoding="utf-8")

    assert "usable_feature_cols" in factor or "usable_fields" in factor
    assert "manifest" in training.lower()
    assert "used_in_model" in events
    assert "event_factor_inputs" in events or "入模事件" in events
