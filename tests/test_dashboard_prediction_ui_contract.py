from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"


def _read(path: str) -> str:
    return (FRONTEND / path).read_text(encoding="utf-8")


def test_dashboard_contains_system_status_banner_and_six_core_cards() -> None:
    dashboard = _read("src/pages/DashboardPage.tsx")
    assert "SystemStatusBanner" in dashboard
    for label in ["系统状态", "主合约与最新价格", "数据质量", "当前研究信号", "模型状态", "风险状态"]:
        assert label in dashboard


def test_system_status_banner_contains_customer_level_states() -> None:
    banner = _read("src/components/dashboard/SystemStatusBanner.tsx")
    for text in [
        "系统运行正常，当前结果仅供投研参考。",
        "部分外部数据源未配置，系统已使用可用数据运行。",
        "数据质量不足，预测已降级为研究观察。",
        "暂无可用 active 模型，当前仅展示研究框架和数据状态。",
        "模型健康状态下降，已停止显示交易点位。",
        "本地服务暂时不可用，请稍后重试或查看日志。",
    ]:
        assert text in banner


def test_prediction_page_has_tabs_empty_state_and_action_buttons() -> None:
    page = _read("src/pages/PredictionPage.tsx")
    for label in ["日内", "1日", "3日", "5日", "10日", "20日", "趋势"]:
        assert label in page
    assert "暂无可用预测结果。请检查数据源配置、模型状态或运行预测任务。" in page
    assert "刷新终端快照" in page
    assert "前往设置" in page
    assert "查看数据源状态" in page
    assert "查看模型治理" in page


def test_prediction_card_uses_collapsible_sections_and_trade_point_guard() -> None:
    card = _read("src/components/prediction/PredictionCard.tsx")
    debug = _read("src/components/common/CollapsibleDebug.tsx")
    for label in ["决策说明", "因子明细", "事件依据", "回测摘要", "技术明细"]:
        assert label in card or label in debug
    assert "暂无交易点位" in card
    assert "非交易建议，仅作投研观察" in card
    assert "方向不明确" in card
    assert "Trade Edge" in card


def test_frontend_sources_do_not_expose_invalid_values_or_forbidden_promises() -> None:
    text = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (FRONTEND / "src").rglob("*")
        if path.is_file() and path.suffix in {".ts", ".tsx", ".css", ".html", ".json"}
    )
    for forbidden in ["保证盈利", "建议买入", "建议卖出", "稳赚"]:
        assert forbidden not in text
    card = _read("src/components/prediction/PredictionCard.tsx")
    assert ">undefined<" not in card
    assert ">null<" not in card
    assert ">NaN<" not in card
