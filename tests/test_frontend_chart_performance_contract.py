from __future__ import annotations

from pathlib import Path


def test_chartbox_uses_lazy_echarts_resize_observer_and_dispose() -> None:
    chart_box = Path("frontend/src/components/charts/ChartBox.tsx").read_text(encoding="utf-8")

    assert "lazy(" in chart_box
    assert "import(\"echarts-for-react\")" in chart_box
    assert "ResizeObserver" in chart_box
    assert "dispose" in chart_box
    assert "import ReactECharts from" not in chart_box


def test_chart_components_have_professional_empty_states_and_short_legends() -> None:
    price_chart = Path("frontend/src/components/charts/PriceChart.tsx").read_text(encoding="utf-8")
    equity_chart = Path("frontend/src/components/charts/EquityCurveChart.tsx").read_text(encoding="utf-8")
    drawdown_chart = Path("frontend/src/components/charts/DrawdownChart.tsx").read_text(encoding="utf-8")

    assert "EmptyState" in price_chart
    assert "markLine" in price_chart
    assert "volume" in price_chart
    assert "legend" in price_chart
    assert "research_only" in equity_chart or "研究" in equity_chart
    assert "formatPercent" in drawdown_chart


def test_vite_keeps_echarts_in_separate_chunk() -> None:
    vite_config = Path("frontend/vite.config.ts").read_text(encoding="utf-8")

    assert "manualChunks" in vite_config
    assert "echarts" in vite_config
