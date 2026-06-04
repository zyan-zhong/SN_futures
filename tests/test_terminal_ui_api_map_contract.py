from __future__ import annotations

from pathlib import Path


PAGES = [
    "总览",
    "行情监控",
    "新闻与事件",
    "因子研究",
    "训练数据",
    "模型研究",
    "回测验证",
    "预测观察",
    "报告中心",
    "设置与诊断",
    "Artifact Center",
]


def test_terminal_ui_api_map_documents_every_primary_page() -> None:
    doc = Path("docs/TERMINAL_UI_API_MAP.md").read_text(encoding="utf-8")

    for page in PAGES:
        assert page in doc
    for heading in ["使用 API", "按钮", "图表", "表格", "空状态", "错误状态", "后端文件来源", "是否可用"]:
        assert heading in doc
    for endpoint in [
        "/api/terminal/summary",
        "/api/terminal/charts/price-history",
        "/api/terminal/events/news",
        "/api/terminal/factors/coverage",
        "/api/terminal/training-dataset/status",
        "/api/terminal/research/backtest-report",
        "/api/terminal/settings/status",
    ]:
        assert endpoint in doc
