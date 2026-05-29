from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def read(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def test_sidebar_has_professional_workbench_navigation():
    source = read("components/layout/Sidebar.tsx")
    for label in [
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
    ]:
        assert label in source


def test_app_routes_market_and_training_pages():
    source = read("App.tsx")
    assert '"market"' in source
    assert '"training"' in source
    assert "MarketMonitorPage" in source
    assert "TrainingDataPage" in source


def test_artifact_center_is_visible_from_reports_page():
    report_source = read("pages/ReportsPage.tsx")
    artifact_source = read("components/artifacts/ArtifactCenter.tsx")
    assert "ArtifactCenter" in report_source
    assert "资料归档 Artifact Center" in artifact_source
    assert "getResearchArtifacts" in artifact_source
    assert "复制诊断摘要" in artifact_source


def test_prediction_page_has_no_active_explanation():
    source = read("pages/PredictionPage.tsx")
    assert "暂无通过 promotion gate 的 active model" in source
    assert "不显示 baseline" in source
    assert "刷新 active prediction" in source


def test_backtest_page_marks_research_backtest_boundary():
    source = read("pages/BacktestPage.tsx")
    assert "研究型收益曲线" in source
    assert "研究回测，不代表 live active 预测，不构成投资建议" in source
    assert "DSR" in source
    assert "PBO" in source
    assert "Reality Check" in source
