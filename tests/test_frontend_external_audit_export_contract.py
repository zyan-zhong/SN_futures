from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendExternalAuditExportContractTest(unittest.TestCase):
    def test_frontend_exposes_external_audit_export_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getExternalAuditExport", terminal)
        self.assertIn("refreshExternalAuditExport", terminal)
        self.assertIn("/api/terminal/governance/external-audit-export", terminal)
        self.assertIn("/api/terminal/governance/refresh-external-audit-export", terminal)
        self.assertIn("ExternalAuditExportPayload", types)
        self.assertIn("review_summary_path", types)
        self.assertIn("redacted_fields", types)
        self.assertIn("omitted_sensitive_files", types)

    def test_governance_console_renders_external_audit_export_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("External Audit Export", page)
        self.assertIn("export status", page)
        self.assertIn("export root", page)
        self.assertIn("evidence file count", page)
        self.assertIn("missing/incomplete reports", page)
        self.assertIn("redaction status", page)
        self.assertIn("review summary path", page)
        self.assertIn("Refresh audit export", page)

    def test_governance_console_does_not_expose_export_of_raw_sensitive_data(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8").lower()

        self.assertNotIn(">export raw managed rows<", page)
        self.assertNotIn(">export customer predictions<", page)
        self.assertNotIn(">export raw token<", page)


if __name__ == "__main__":
    unittest.main()
