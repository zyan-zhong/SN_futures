from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendRealDataApiContractTest(unittest.TestCase):
    def test_terminal_client_contains_prompt_26_display_apis(self) -> None:
        source = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        for token in (
            "refreshAll",
            "refreshMarket",
            "refreshNews",
            "refreshPredictions",
            "refreshReports",
            "getRefreshHistory",
            "getPriceHistory",
            "getForecastPath",
            "getNewsEvents",
            "getEventEvidence",
            "getFullReport",
            "getFactorDiagnostics",
        ):
            self.assertIn(token, source)

    def test_dashboard_mounts_refresh_and_price_history_chart(self) -> None:
        dashboard = (FRONTEND / "pages" / "DashboardPage.tsx").read_text(encoding="utf-8")
        refresh_panel = (FRONTEND / "components" / "data" / "RefreshTaskPanel.tsx").read_text(encoding="utf-8")
        self.assertIn("RefreshTaskPanel", dashboard)
        self.assertIn("getPriceHistory", dashboard)
        self.assertIn("一键刷新数据", refresh_panel)

    def test_prediction_page_uses_forecast_path_and_refresh_guidance(self) -> None:
        source = (FRONTEND / "pages" / "PredictionPage.tsx").read_text(encoding="utf-8")
        self.assertIn("getForecastPath", source)
        self.assertIn("ForecastPathChart", source)
        self.assertIn("一键刷新数据", source)
        self.assertIn("生成预测", source)
        self.assertIn("查看运行期诊断", source)

    def test_event_report_and_factor_pages_use_new_apis(self) -> None:
        event_page = (FRONTEND / "pages" / "EventPage.tsx").read_text(encoding="utf-8")
        reports_page = (FRONTEND / "pages" / "ReportsPage.tsx").read_text(encoding="utf-8")
        factor_page = (FRONTEND / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")
        self.assertIn("getNewsEvents", event_page)
        self.assertIn("getFullReport", reports_page)
        self.assertIn("getFactorDiagnostics", factor_page)
        self.assertIn("暂无完整因子诊断数据", factor_page)
        self.assertIn("点击生成报告", reports_page)

    def test_frontend_still_has_no_promises_or_key_storage(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in FRONTEND.rglob("*")
            if path.is_file() and path.suffix in {".ts", ".tsx", ".css", ".html", ".json"}
        )
        for forbidden in ("保证盈利", "建议买入", "建议卖出", "稳赚", "localStorage.setItem(\"SN_"):
            self.assertNotIn(forbidden, text)


if __name__ == "__main__":
    unittest.main()
