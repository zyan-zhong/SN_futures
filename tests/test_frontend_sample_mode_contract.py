from __future__ import annotations

from pathlib import Path


ROOT = Path("frontend/src")


def read(path: str) -> str:
    return (Path(path)).read_text(encoding="utf-8")


def test_frontend_contains_sample_mode_banner_and_toggle() -> None:
    assert Path("frontend/src/components/common/SampleModeBanner.tsx").exists()
    app = read("frontend/src/App.tsx")
    banner = read("frontend/src/components/common/SampleModeBanner.tsx")
    settings = read("frontend/src/pages/SettingsPage.tsx")
    assert "样例数据模式" in banner
    assert "showSampleData" in app
    assert "是否显示样例数据" in settings


def test_frontend_marks_sample_charts_and_copy() -> None:
    price_chart = read("frontend/src/components/charts/PriceChart.tsx")
    forecast_chart = read("frontend/src/components/charts/ForecastPathChart.tsx")
    assert "Sample / 样例" in price_chart
    assert "Sample / 样例" in forecast_chart


def test_frontend_does_not_treat_sample_as_trade_advice() -> None:
    combined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in ROOT.rglob("*.tsx"))
    assert "建议买入" not in combined
    assert "建议卖出" not in combined
    assert "保证盈利" not in combined
    assert "稳赚" not in combined
    assert "暂无交易点位" in combined
