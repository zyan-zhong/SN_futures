from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxyQuarantineSnapshotContractTest(unittest.TestCase):
    def test_frontend_api_exposes_quarantine_snapshot_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ManagedProxyQuarantineSnapshotPayload", types)
        self.assertIn("getManagedProxyQuarantineSnapshot", terminal)
        self.assertIn("pullManagedProxyQuarantineSnapshot", terminal)
        self.assertIn("/api/terminal/managed-proxy/quarantine-snapshot", terminal)
        self.assertIn("/api/terminal/managed-proxy/pull-quarantine-snapshot", terminal)

    def test_data_status_page_renders_quarantined_snapshot_card_without_secret_inputs(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Quarantined Snapshot", page)
        self.assertIn("snapshot status", page)
        self.assertIn("row budget", page)
        self.assertIn("snapshot_row_count", page)
        self.assertIn("quarantine path", page.lower())
        self.assertIn("schema/timestamp coverage", page.lower())
        self.assertIn("redacted preview status", page.lower())
        self.assertIn("quarantine snapshot cannot unlock v12", page.lower())
        self.assertIn("Pull quarantine snapshot", page)
        self.assertNotIn('type="password"', page)
        self.assertNotIn("raw token input", page.lower())
        self.assertNotIn("custom output path", page.lower())


if __name__ == "__main__":
    unittest.main()
