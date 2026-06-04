from __future__ import annotations

from pathlib import Path


def test_frontend_market_monitor_exposes_analysis_not_prediction() -> None:
    terminal_api = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
    types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")
    page = Path("frontend/src/pages/MarketMonitorPage.tsx").read_text(encoding="utf-8")
    backend = Path("src/sn_futures/api/terminal_api.py").read_text(encoding="utf-8")

    assert "getMarketAnalysis" in terminal_api
    assert '"/api/terminal/market-analysis"' in terminal_api
    assert "MarketAnalysisPayload" in types
    assert "专业行情分析" in page
    assert "这是行情分析，不是预测" in page
    assert "趋势结构" in page
    assert "波动状态" in page
    assert "关键价位" in page
    assert "数据缺口" in page
    assert "/api/terminal/market-analysis" in backend
