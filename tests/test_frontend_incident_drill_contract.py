from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendIncidentDrillContractTest(unittest.TestCase):
    def test_frontend_exposes_incident_drill_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getIncidentDrill", terminal)
        self.assertIn("runIncidentDrill", terminal)
        self.assertIn("refreshLockdownState", terminal)
        self.assertIn("/api/terminal/governance/incident-drill", terminal)
        self.assertIn("/api/terminal/governance/run-incident-drill", terminal)
        self.assertIn("/api/terminal/governance/refresh-lockdown-state", terminal)
        self.assertIn("IncidentDrillPayload", types)
        self.assertIn("lockdown_triggered", types)
        self.assertIn("remediation_playbook", types)

    def test_governance_console_renders_incident_drill_lockdown_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Incident Drill / Lockdown", page)
        self.assertIn("lockdown status", page)
        self.assertIn("scenarios", page)
        self.assertIn("remediation playbook", page)
        self.assertIn("forbidden actions", page)
        self.assertIn("manual unlock required", page)
        self.assertIn("Run incident drill", page)
        self.assertIn("Refresh lockdown state", page)

    def test_governance_console_does_not_expose_real_break_glass_write_buttons(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8").lower()

        for phrase in [
            "write active",
            "generate customer prediction",
            "save raw token",
            "disable lockdown",
            "manual unlock now",
        ]:
            self.assertNotIn(f">{phrase}<", page)


if __name__ == "__main__":
    unittest.main()
