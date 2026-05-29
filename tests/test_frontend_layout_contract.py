from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_sidebar_uses_customer_task_navigation():
    source = _read(FRONTEND / "src" / "components" / "layout" / "Sidebar.tsx")
    for label in ["总览", "刷新与数据源", "行情与新闻", "预测观察", "回测验证", "报告中心", "设置与诊断"]:
        assert label in source
    assert "高级模式 / 技术明细" in source
    assert "模型治理" in source
    assert "因子诊断" in source


def test_global_layout_prevents_page_overflow():
    css = _read(FRONTEND / "src" / "styles" / "globals.css")
    assert "overflow-x: hidden" in css
    assert "max-width: 100vw" in css
    assert "min-width: 0" in css
    assert "overflow-wrap: anywhere" in css
    assert ".data-table-wrap" in css and "overflow-x: auto" in css
    assert ".advanced-nav" in css


def test_status_and_market_color_semantics_are_separated():
    css = _read(FRONTEND / "src" / "styles" / "globals.css")
    tokens = _read(FRONTEND / "src" / "utils" / "colorTokens.ts")
    assert "banner-ok" in css
    assert "market-up" in css
    assert "market-down" in css
    assert "price_up" in tokens and "#f15f5f" in tokens
    assert "price_down" in tokens and "#49c6a7" in tokens
    assert "system_ok" in tokens


def test_playwright_layout_checks_cover_required_viewports():
    spec = _read(FRONTEND / "e2e" / "terminal.spec.ts")
    for viewport in ["layout-1366", "layout-1280", "layout-1024", "layout-tablet", "layout-mobile"]:
        assert viewport in spec
    assert "scrollWidth" in spec
    assert "刷新与数据源" in spec
    assert "行情与新闻" in spec
    assert "预测观察" in spec
