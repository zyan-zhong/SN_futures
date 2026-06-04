from __future__ import annotations

from pathlib import Path


def test_pages_have_professional_empty_or_error_states() -> None:
    required_pages = [
        "BacktestPage.tsx",
        "EventPage.tsx",
        "FactorPage.tsx",
        "PredictionPage.tsx",
        "ReportsPage.tsx",
        "TrainingDataPage.tsx",
        "MarketMonitorPage.tsx",
    ]
    for page in required_pages:
        text = Path("frontend/src/pages", page).read_text(encoding="utf-8")
        assert "EmptyState" in text or "CompactEmptyState" in text or "ErrorState" in text


def test_no_forbidden_or_raw_placeholder_text_is_visible_in_pages() -> None:
    joined = "\n".join(path.read_text(encoding="utf-8") for path in Path("frontend/src/pages").glob("*.tsx"))
    forbidden = ["建议买入", "建议卖出", "保证盈利", "fake prediction", ">undefined<", ">null<", ">NaN<"]
    for phrase in forbidden:
        assert phrase not in joined


def test_compact_ui_support_components_exist() -> None:
    for component in [
        "CompactStatusCard.tsx",
        "CompactEmptyState.tsx",
        "TechnicalDetailsDrawer.tsx",
        "PageToolbar.tsx",
        "ApiHealthBadge.tsx",
        "DataFreshnessBadge.tsx",
    ]:
        assert Path("frontend/src/components/common", component).exists()
