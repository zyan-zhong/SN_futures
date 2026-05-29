from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_settings_page_inputs_have_labels_and_no_key_localstorage() -> None:
    source = _read(SRC / "pages" / "SettingsPage.tsx")
    assert "<label" in source or "aria-label" in source
    assert "password" in source
    assert "密钥仅保存在本机用户目录" in source
    assert "localStorage" not in source


def test_collapsible_debug_is_keyboard_friendly_and_collapsed() -> None:
    source = _read(SRC / "components" / "common" / "CollapsibleDebug.tsx")
    assert "<details" in source
    assert "<summary" in source
    assert "open" not in source


def test_responsive_breakpoints_and_focus_styles_exist() -> None:
    css = _read(SRC / "styles" / "globals.css")
    assert "@media (min-width: 1440px)" in css
    assert "@media (min-width: 1024px) and (max-width: 1439px)" in css
    assert "@media (min-width: 768px) and (max-width: 1023px)" in css
    assert "@media (max-width: 767px)" in css
    assert "overflow-x: hidden" in css
    assert "focus-visible" in css


def test_charts_keep_empty_state_text() -> None:
    chart_sources = "\n".join(
        path.read_text(encoding="utf-8") for path in (SRC / "components" / "charts").glob("*.tsx")
    )
    assert "暂无可用图表数据" in chart_sources or "暂无概率图数据" in chart_sources
    assert "ChartBox" in chart_sources


def test_data_table_supports_horizontal_scroll() -> None:
    table_source = _read(SRC / "components" / "common" / "DataTable.tsx")
    css = _read(SRC / "styles" / "globals.css")
    assert "data-table-wrap" in table_source
    assert "overflow-x: auto" in css
