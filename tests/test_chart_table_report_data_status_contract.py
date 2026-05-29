from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _read(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def test_chart_components_have_empty_state_and_chart_shell() -> None:
    for path in [
        "src/components/charts/PriceChart.tsx",
        "src/components/charts/EquityCurveChart.tsx",
        "src/components/charts/DrawdownChart.tsx",
        "src/components/charts/FactorBarChart.tsx",
        "src/components/charts/ProbabilityGauge.tsx",
    ]:
        source = _read(path)
        assert "暂无" in source
        assert "ChartBox" in source
    chart_box = _read("src/components/charts/ChartBox.tsx")
    assert "minHeight" in chart_box
    assert "ResizeObserver" in chart_box
    assert "dispose" in chart_box


def test_data_table_exists_and_handles_empty_loading_error_states() -> None:
    table = _read("src/components/common/DataTable.tsx")
    assert "暂无可用数据" in table
    assert "LoadingState" in table
    assert "ErrorState" in table
    assert "data-table-wrap" in table
    assert "formatPercent" in table
    assert "formatDateTime" in table


def test_report_center_has_markdown_preview_copy_download_and_no_nan_copy() -> None:
    report = _read("src/components/reports/ReportCenter.tsx")
    assert "暂无报告，请先运行报告生成任务。" in report
    assert "复制 Markdown" in report
    assert "下载 .md" in report
    assert "不构成投资建议" in report
    assert "replace(/\\bnan\\b/gi" in report


def test_data_status_page_explains_states_and_does_not_show_keys() -> None:
    panel = _read("src/components/data/DataSourceStatusPanel.tsx")
    for text in ["正常：数据源可用", "未配置：需要在设置页配置 key", "数据源失败：请求失败或服务不可用", "使用缓存：当前展示缓存数据", "已过期：超过更新周期"]:
        assert text in panel
    assert "前往设置" in panel
    assert "刷新状态" in panel
    assert "查看日志位置" in panel
    assert "SN_ALPHA_VANTAGE_KEY" not in panel
    assert "SN_NEWSAPI_KEY" not in panel


def test_frontend_sources_still_have_no_profit_promises_or_trade_advice() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (FRONTEND / "src").rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx", ".css", ".html", ".json"}
    )
    for forbidden in ["保证盈利", "建议买入", "建议卖出", "稳赚"]:
        assert forbidden not in text

