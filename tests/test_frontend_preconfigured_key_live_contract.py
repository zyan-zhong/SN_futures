from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class FrontendPreconfiguredKeyLiveContractTest(unittest.TestCase):
    def test_frontend_exposes_private_key_validation_flow_without_full_key_storage(self) -> None:
        settings = Path("frontend/src/pages/SettingsPage.tsx").read_text(encoding="utf-8")
        event_page = Path("frontend/src/pages/EventPage.tsx").read_text(encoding="utf-8")
        data_status = Path("frontend/src/pages/DataStatusPage.tsx").read_text(encoding="utf-8")
        client = Path("frontend/src/api/terminal.ts").read_text(encoding="utf-8")

        self.assertIn("NewsAPI", settings)
        self.assertIn("Alpha Vantage", settings)
        self.assertIn("source", settings)
        self.assertIn("masked", settings)
        self.assertIn("/api/terminal/newsapi/test", client)
        self.assertIn("/api/terminal/refresh/${kind}", client)
        self.assertIn('"cross-market"', client)
        self.assertIn("relevance_score", event_page)
        self.assertIn("used_in_model", event_page)
        self.assertIn("exclusion_reason", event_page)
        self.assertIn("CSV/Excel", data_status)
        self.assertNotIn("localStorage.setItem(\"SN_ALPHA_VANTAGE_KEY", settings)
        self.assertNotIn("localStorage.setItem(\"SN_NEWSAPI_KEY", settings)


if __name__ == "__main__":
    unittest.main()
