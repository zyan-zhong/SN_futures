from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendPromotionDryRunEvidenceContractTest(unittest.TestCase):
    def test_frontend_exposes_promotion_dry_run_evidence_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getPromotionDryRunEvidence", terminal)
        self.assertIn("refreshPromotionDryRunEvidence", terminal)
        self.assertIn("/api/terminal/governance/promotion-dry-run-evidence", terminal)
        self.assertIn("/api/terminal/governance/refresh-promotion-dry-run-evidence", terminal)
        self.assertIn("PromotionDryRunEvidencePayload", types)
        self.assertIn("simulated_registry_write_plan", types)
        self.assertIn("artifact_boundary_checks", types)
        self.assertIn("active_write_attempted", types)

    def test_governance_console_renders_promotion_dry_run_evidence_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Promotion Dry-Run Evidence", page)
        self.assertIn("promotion dry-run status", page)
        self.assertIn("precondition checks", page)
        self.assertIn("simulated registry write plan", page)
        self.assertIn("artifact boundary checks", page)
        self.assertIn("active/customer prediction confirmation", page)
        self.assertIn("Refresh promotion dry-run evidence", page)

    def test_governance_console_does_not_expose_real_promotion_or_prediction_buttons(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8").lower()

        self.assertNotIn(">run real promotion<", page)
        self.assertNotIn(">publish active<", page)
        self.assertNotIn(">write active model<", page)
        self.assertNotIn(">generate customer prediction<", page)
        self.assertNotIn(">train candidate<", page)


if __name__ == "__main__":
    unittest.main()
