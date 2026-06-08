from __future__ import annotations

from pathlib import Path


def _api_client_surface() -> str:
    api_dir = Path("frontend/src/api")
    return "\n".join(
        (api_dir / name).read_text(encoding="utf-8")
        for name in ("terminal.ts", "backtest.ts")
    )


def test_each_chart_component_is_backed_by_named_terminal_data_source() -> None:
    terminal_api = _api_client_surface()
    chart_sources = {
        "PriceChart": ["/api/terminal/charts/price-history", "getPriceHistory"],
        "ForecastPathChart": ["/api/terminal/charts/forecast-path", "getForecastPath"],
        "EquityCurveChart": ["/api/terminal/research/equity-curve", "getResearchEquityCurve"],
        "DrawdownChart": ["/api/terminal/research/backtest-report", "getResearchBacktestReport"],
        "FactorBarChart": ["/api/terminal/factors/coverage", "getFeatureCoverage"],
    }
    for component, needles in chart_sources.items():
        assert Path(f"frontend/src/components/charts/{component}.tsx").exists()
        for needle in needles:
            assert needle in terminal_api


def test_visualizations_do_not_render_prediction_path_without_active_status() -> None:
    prediction_page = Path("frontend/src/pages/PredictionPage.tsx").read_text(encoding="utf-8")
    forecast_chart = Path("frontend/src/components/charts/ForecastPathChart.tsx").read_text(encoding="utf-8")

    assert "hasActive" in prediction_page
    assert "暂无 active prediction path" in prediction_page
    assert "fake" not in forecast_chart.lower()
