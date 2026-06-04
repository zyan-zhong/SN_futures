from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendGovernanceAccessControlContractTest(unittest.TestCase):
    def test_frontend_exposes_access_control_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getGovernanceAccessControl", terminal)
        self.assertIn("refreshGovernanceAccessControl", terminal)
        self.assertIn("/api/terminal/governance/access-control", terminal)
        self.assertIn("/api/terminal/governance/refresh-access-control", terminal)
        self.assertIn("GovernanceAccessControlPayload", types)
        self.assertIn("permission_matrix", types)
        self.assertIn("api_action_inventory", types)
        self.assertIn("ui_action_inventory", types)
        self.assertIn("blocked_secret_actions", types)

    def test_governance_console_renders_access_control_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Access Control", page)
        self.assertIn("permission matrix summary", page)
        self.assertIn("blocked heavy actions", page)
        self.assertIn("blocked secret actions", page)
        self.assertIn("UI/API action inventory", page)
        self.assertIn("active_write_allowed", page)
        self.assertIn("customer_prediction_write_allowed", page)
        self.assertIn("Refresh access control", page)

    def test_governance_console_still_has_no_high_risk_action_buttons(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")
        lower_page = page.lower()

        for helper in [
            "approveActiveModel",
            "saveSettingsSecrets",
            "refreshPredictions",
            "runCandidateV",
            "buildFeatureStore",
            "buildTrainingDataset",
            "promoteCandidateModel",
        ]:
            self.assertNotIn(helper, page)

        for phrase in [
            "publish active",
            "generate customer prediction",
            "raw token",
            "authorization header",
            "build feature store",
            "train candidate",
        ]:
            self.assertNotIn(f">{phrase}<", lower_page)


if __name__ == "__main__":
    unittest.main()
