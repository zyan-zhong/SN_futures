from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


def read(relative: str) -> str:
    return (FRONTEND / relative).read_text(encoding="utf-8")


def test_dashboard_defaults_to_no_sample_price_history_and_blocked_prediction_copy() -> None:
    page = read("pages/DashboardPage.tsx")

    assert "showSampleData = false" in page
    assert "LocalFirstStatusPanel" in page
    assert "PredictionBlockedEmptyState" in page
    assert "暂无真实预测" in page
    assert "数据源未配置" in page
    assert "预测已阻断" in page
    assert "sample price history" not in page.lower()


def test_terminal_overview_prioritizes_local_setup_and_moves_managed_v12_to_advanced() -> None:
    page = read("pages/TerminalOverviewPage.tsx")

    assert "LocalFirstStatusPanel" in page
    assert "PredictionBlockedEmptyState" in page
    assert "System Readiness" in page
    assert "Advanced Diagnostics / Research Governance" in page
    assert "<details" in page
    assert "Managed Proxy / v12 chain" in page
    assert page.index("System Readiness") < page.index("Advanced Diagnostics / Research Governance")


def test_data_status_default_path_starts_with_local_provider_matrix() -> None:
    page = read("pages/DataStatusPage.tsx")
    panel = read("components/setup/LocalProviderSetupPanel.tsx")
    helper = read("utils/localFirstStatus.ts")

    assert "LocalProviderSetupPanel" in page
    assert "Provider Setup Matrix" in panel
    assert "Alpha Vantage" in helper
    assert "NewsAPI" in helper
    assert "Tushare" in helper
    assert "Local API Provider" in helper
    assert "Advanced Diagnostics" in page
    assert "<details" in page
    assert page.index("LocalProviderSetupPanel") < page.index("Advanced Diagnostics")


def test_frontend_has_local_first_helpers_and_no_fake_prediction_terms() -> None:
    helper = read("utils/localFirstStatus.ts")
    empty_state = read("components/setup/PredictionBlockedEmptyState.tsx")
    guided_setup = read("utils/guidedSetup.ts")
    combined_pages = "\n".join(
        read(path)
        for path in [
            "pages/DashboardPage.tsx",
            "pages/TerminalOverviewPage.tsx",
            "pages/PredictionWorkspacePage.tsx",
        ]
    )

    assert "buildLocalFirstStatusModel" in helper
    assert "getPredictionEmptyState" in helper
    assert "getProviderSetupCards" in helper
    assert "deriveBlockedPredictionExplanation" in empty_state
    assert "暂无真实预测" in guided_setup
    assert "研究参考，不构成投资建议" in guided_setup
    for forbidden in ["强烈看多", "强烈看空", "sample prediction", "baseline forecast"]:
        assert forbidden not in combined_pages
