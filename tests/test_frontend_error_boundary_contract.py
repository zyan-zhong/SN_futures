from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SRC = FRONTEND / "src"


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_error_boundary_exists_and_uses_chinese_fallback() -> None:
    source = _read(SRC / "components" / "common" / "ErrorBoundary.tsx")
    assert "该模块暂时无法显示" in source
    assert "技术明细 / 开发调试信息" in source or "COPY.debugTitle" in source
    assert "<details" in source
    assert "sanitizeRecord" in source


def test_app_shell_and_charts_are_wrapped_by_error_boundary() -> None:
    app_shell = _read(SRC / "components" / "layout" / "AppShell.tsx")
    chart_box = _read(SRC / "components" / "charts" / "ChartBox.tsx")
    assert "ErrorBoundary" in app_shell
    assert 'moduleName="主内容区域"' in app_shell
    assert "ErrorBoundary" in chart_box
    assert "role=\"img\"" in chart_box


def test_key_pages_have_module_level_error_boundaries() -> None:
    for relative in [
        "pages/DashboardPage.tsx",
        "pages/PredictionPage.tsx",
        "pages/BacktestPage.tsx",
        "pages/ModelGovernancePage.tsx",
        "pages/PositionPage.tsx",
        "pages/ReportsPage.tsx",
        "pages/DataStatusPage.tsx",
    ]:
        assert "ErrorBoundary" in _read(SRC / relative), relative


def test_loading_empty_error_states_support_customer_actions() -> None:
    loading = _read(SRC / "components" / "common" / "LoadingState.tsx")
    empty = _read(SRC / "components" / "common" / "EmptyState.tsx")
    error = _read(SRC / "components" / "common" / "ErrorState.tsx")
    assert "正在加载本地终端数据" in loading
    assert "actionLabel" in empty and "secondaryActionLabel" in empty
    assert "actionLabel" in error and "secondaryActionLabel" in error
    assert "<details" in error
