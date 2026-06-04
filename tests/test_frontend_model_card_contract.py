from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendModelCardContractTest(unittest.TestCase):
    def test_frontend_exposes_model_card_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getModelCard", terminal)
        self.assertIn("refreshModelCard", terminal)
        self.assertIn("/api/terminal/governance/model-card", terminal)
        self.assertIn("/api/terminal/governance/refresh-model-card", terminal)
        self.assertIn("ModelCardPayload", types)
        self.assertIn("risk_disclosure", types)
        self.assertIn("gate_failures", types)
        self.assertIn("no_active_confirmation", types)

    def test_governance_console_renders_model_card_risk_disclosure_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Model Card / Risk Disclosure", page)
        self.assertIn("current status", page)
        self.assertIn("intended use", page)
        self.assertIn("prohibited use", page)
        self.assertIn("key limitations", page)
        self.assertIn("gate failures", page)
        self.assertIn("model_card.md path", page)
        self.assertIn("risk_disclosure.md path", page)
        self.assertIn("no-active/no-prediction confirmation", page)
        self.assertIn("Refresh model card", page)

    def test_governance_console_does_not_expose_active_or_customer_prediction_actions(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8").lower()

        self.assertNotIn(">publish active<", page)
        self.assertNotIn(">write active model<", page)
        self.assertNotIn(">generate customer prediction<", page)
        self.assertNotIn(">train candidate<", page)


if __name__ == "__main__":
    unittest.main()
