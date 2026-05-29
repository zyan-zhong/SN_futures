from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_factor_page_mentions_institutional_factor_sections() -> None:
    text = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")
    for phrase in ("机构级因子覆盖率", "基差因子状态", "库存/仓单因子状态", "外盘/汇率因子状态", "新闻相关性状态"):
        assert phrase in text


def test_event_page_shows_relevance_and_model_usage() -> None:
    text = (ROOT / "frontend" / "src" / "pages" / "EventPage.tsx").read_text(encoding="utf-8")
    for phrase in ("高相关事件", "低相关新闻折叠", "入模/未入模", "相关性分数"):
        assert phrase in text


def test_frontend_does_not_add_customer_prediction_shortcuts() -> None:
    joined = "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (ROOT / "frontend" / "src").rglob("*.*") if path.suffix in {".ts", ".tsx"})
    forbidden = ("baseline forecast", "baseline backtest", "基线预测", "基线回测", "fake prediction")
    for phrase in forbidden:
        assert phrase not in joined

