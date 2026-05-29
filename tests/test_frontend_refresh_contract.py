from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendRefreshContractTest(unittest.TestCase):
    def test_refresh_panel_exists_and_contains_one_click_refresh(self) -> None:
        panel = FRONTEND / "components" / "data" / "RefreshTaskPanel.tsx"
        self.assertTrue(panel.exists())
        text = panel.read_text(encoding="utf-8")
        self.assertIn("一键刷新数据", text)
        self.assertIn("刷新行情", text)
        self.assertIn("刷新新闻", text)
        self.assertNotIn("localStorage", text)
        self.assertNotIn("SN_ALPHA_VANTAGE_KEY", text)
        self.assertNotIn("SN_NEWSAPI_KEY", text)

    def test_dashboard_and_data_status_mount_refresh_panel(self) -> None:
        dashboard = (FRONTEND / "pages" / "DashboardPage.tsx").read_text(encoding="utf-8")
        data_status = (FRONTEND / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")
        self.assertIn("RefreshTaskPanel", dashboard)
        self.assertIn("RefreshTaskPanel", data_status)

    def test_terminal_client_uses_refresh_api(self) -> None:
        client = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        self.assertIn("/api/terminal/refresh/status", client)
        self.assertIn("/api/terminal/refresh/", client)


if __name__ == "__main__":
    unittest.main()
