from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendProductionCutoverContractTest(unittest.TestCase):
    def test_frontend_exposes_cutover_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getProductionCutoverChecklist", terminal)
        self.assertIn("refreshProductionCutoverChecklist", terminal)
        self.assertIn("buildNoopReleasePlan", terminal)
        self.assertIn("/api/terminal/governance/production-cutover-checklist", terminal)
        self.assertIn("/api/terminal/governance/refresh-production-cutover-checklist", terminal)
        self.assertIn("/api/terminal/governance/build-noop-release-plan", terminal)
        self.assertIn("ProductionCutoverChecklistPayload", types)
        self.assertIn("cutover_allowed", types)
        self.assertIn("noop_release_plan_ready", types)
        self.assertIn("rollback_plan_summary", types)

    def test_governance_console_renders_production_cutover_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Production Cutover Checklist", page)
        self.assertIn("cutover_allowed", page)
        self.assertIn("noop plan status", page)
        self.assertIn("precondition checks", page)
        self.assertIn("required manual steps", page)
        self.assertIn("forbidden actions", page)
        self.assertIn("rollback plan summary", page)
        self.assertIn("Refresh cutover checklist", page)
        self.assertIn("Build no-op release plan", page)

    def test_governance_console_does_not_expose_active_or_prediction_cutover_buttons(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8").lower()

        self.assertNotIn(">publish active<", page)
        self.assertNotIn(">run promotion<", page)
        self.assertNotIn(">generate customer prediction<", page)
        self.assertNotIn(">train candidate<", page)


if __name__ == "__main__":
    unittest.main()
