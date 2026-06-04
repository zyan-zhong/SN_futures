from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendManualApprovalContractTest(unittest.TestCase):
    def test_frontend_exposes_manual_approval_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getManualApproval", terminal)
        self.assertIn("refreshManualApproval", terminal)
        self.assertIn("createManualApprovalRequest", terminal)
        self.assertIn("recordManualApprovalDecision", terminal)
        self.assertIn("/api/terminal/governance/manual-approval", terminal)
        self.assertIn("/api/terminal/governance/refresh-manual-approval", terminal)
        self.assertIn("/api/terminal/governance/create-manual-approval-request", terminal)
        self.assertIn("/api/terminal/governance/record-manual-approval-decision", terminal)
        self.assertIn("ManualApprovalPayload", types)
        self.assertIn("two_person_review_pass", types)
        self.assertIn("precondition_checks", types)

    def test_governance_console_renders_manual_approval_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Manual Approval", page)
        self.assertIn("approval status", page)
        self.assertIn("requested action", page)
        self.assertIn("precondition checks", page)
        self.assertIn("two-person review status", page)
        self.assertIn("expiry", page)
        self.assertIn("active publish is not supported here", page)

    def test_governance_console_does_not_expose_active_or_prediction_approval_buttons(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8").lower()

        for phrase in [
            "approve active",
            "publish active",
            "generate customer prediction",
            "active_publish",
            "customer_prediction",
        ]:
            self.assertNotIn(f">{phrase}<", page)


if __name__ == "__main__":
    unittest.main()
