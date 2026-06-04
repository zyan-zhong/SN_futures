from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ManagedDataAuditFrontendContractTest(unittest.TestCase):
    def test_frontend_api_exposes_pit_audit_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getManagedProxyAudit", terminal)
        self.assertIn("runManagedProxyAudit", terminal)
        self.assertIn("getManagedProxyAuditReadiness", terminal)
        self.assertIn("/api/terminal/managed-proxy/audit", terminal)
        self.assertIn("/api/terminal/managed-proxy/run-audit", terminal)
        self.assertIn("/api/terminal/managed-proxy/audit-readiness", terminal)
        self.assertIn("ManagedProxyAuditPayload", types)
        self.assertIn("leakage_checks", types)

    def test_data_status_page_renders_point_in_time_audit_section(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Point-in-Time Audit", page)
        self.assertIn("timestamp coverage", page)
        self.assertIn("PIT pass/fail", page)
        self.assertIn("required timestamp fields", page)
        self.assertIn("missing timestamp fields", page)
        self.assertIn("lag summary", page)
        self.assertIn("whether Feature Store v12 build is allowed", page)


if __name__ == "__main__":
    unittest.main()
