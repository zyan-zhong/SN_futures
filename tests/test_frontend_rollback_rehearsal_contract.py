from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendRollbackRehearsalContractTest(unittest.TestCase):
    def test_frontend_exposes_rollback_rehearsal_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getRollbackRehearsal", terminal)
        self.assertIn("refreshRollbackRehearsal", terminal)
        self.assertIn("simulateArtifactQuarantine", terminal)
        self.assertIn("/api/terminal/governance/rollback-rehearsal", terminal)
        self.assertIn("/api/terminal/governance/refresh-rollback-rehearsal", terminal)
        self.assertIn("/api/terminal/governance/simulate-artifact-quarantine", terminal)
        self.assertIn("RollbackRehearsalPayload", types)
        self.assertIn("quarantine_needed", types)
        self.assertIn("artifacts_detected", types)
        self.assertIn("simulated_quarantine_actions", types)
        self.assertIn("safety_checks", types)

    def test_governance_console_renders_rollback_rehearsal_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Rollback / Quarantine", page)
        self.assertIn("rehearsal status", page)
        self.assertIn("quarantine_needed", page)
        self.assertIn("artifacts_detected", page)
        self.assertIn("simulated quarantine actions", page)
        self.assertIn("rollback plan", page)
        self.assertIn("manual actions required", page)
        self.assertIn("safety checks", page)
        self.assertIn("Refresh rollback rehearsal", page)
        self.assertIn("Simulate artifact quarantine", page)

    def test_governance_console_has_no_real_quarantine_or_delete_buttons(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")
        lower_page = page.lower()

        for phrase in [
            ">delete artifact<",
            ">move artifact<",
            ">quarantine real artifact<",
            ">remove active model<",
            ">purge customer predictions<",
        ]:
            self.assertNotIn(phrase, lower_page)


if __name__ == "__main__":
    unittest.main()
