from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendPitReplayContractTest(unittest.TestCase):
    def test_frontend_api_exposes_pit_replay_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ManagedPitReplayPayload", types)
        self.assertIn("getManagedPitReplay", terminal)
        self.assertIn("runManagedPitReplay", terminal)
        self.assertIn("/api/terminal/managed-proxy/pit-replay", terminal)
        self.assertIn("/api/terminal/managed-proxy/run-pit-replay", terminal)

    def test_data_status_page_renders_pit_replay_summary(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("PIT Replay", page)
        self.assertIn("cases passed/failed", page)
        self.assertIn("future rows rejected", page)
        self.assertIn("selected row rule", page)
        self.assertIn("Run PIT replay", page)
        self.assertNotIn("buildFeatureStoreV12()", page)


if __name__ == "__main__":
    unittest.main()
