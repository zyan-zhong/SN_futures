from __future__ import annotations

import unittest
from pathlib import Path


class FrontendNewsRelevanceDiagnosticsContractTest(unittest.TestCase):
    def test_event_page_exposes_query_group_and_keyword_evidence(self) -> None:
        event_page = Path("frontend/src/pages/EventPage.tsx").read_text(encoding="utf-8")
        client = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")
        types = Path("frontend/src/api/types.ts").read_text(encoding="utf-8")

        self.assertIn("getNewsRelevanceDiagnostics", client)
        self.assertIn("/api/terminal/events/relevance-diagnostics", client)
        self.assertIn("NewsRelevanceDiagnosticsPayload", types)
        self.assertIn("Query Group", event_page)
        self.assertIn("关键词证据", event_page)
        self.assertIn("真实锡新闻误杀风险", event_page)
        self.assertIn("不会伪造事件因子", event_page)
        self.assertNotIn("localStorage.setItem", event_page)


if __name__ == "__main__":
    unittest.main()
