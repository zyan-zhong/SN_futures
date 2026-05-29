from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class FrontendNewsApiContractTest(unittest.TestCase):
    def test_settings_and_event_pages_expose_newsapi_validation_and_relevance_sections(self) -> None:
        settings = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
        event_page = Path("frontend/src/pages/EventPage.tsx").read_text(encoding="utf-8")
        client = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")

        self.assertIn("测试 NewsAPI", settings)
        self.assertIn("NewsAPI 验证", settings)
        self.assertIn("入模事件", event_page)
        self.assertIn("仅展示新闻", event_page)
        self.assertIn("已排除新闻", event_page)
        self.assertIn("exclusion_reason", event_page)
        self.assertIn("新闻源质量诊断", event_page)
        self.assertIn("source reliability", event_page)
        self.assertIn("hard evidence", event_page)
        self.assertIn("/api/terminal/events/source-quality-report", client)
        self.assertIn("/api/terminal/newsapi/status", client)
        self.assertIn("/api/terminal/newsapi/test", client)
        self.assertNotIn("localStorage.setItem(\"SN_NEWSAPI_KEY", settings)


if __name__ == "__main__":
    unittest.main()
