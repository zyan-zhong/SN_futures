from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendShadowReplayContractTest(unittest.TestCase):
    def test_frontend_exposes_shadow_replay_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getShadowReplay", terminal)
        self.assertIn("refreshShadowReplay", terminal)
        self.assertIn("/api/terminal/governance/shadow-replay", terminal)
        self.assertIn("/api/terminal/governance/refresh-shadow-replay", terminal)
        self.assertIn("ShadowReplayPayload", types)
        self.assertIn("replay_row_count", types)
        self.assertIn("stability_metrics", types)
        self.assertIn("risk_tags", types)

    def test_governance_console_renders_shadow_replay_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Shadow Replay Evaluator", page)
        self.assertIn("source candidate", page)
        self.assertIn("replay rows", page)
        self.assertIn("schema validation", page)
        self.assertIn("output isolation", page)
        self.assertIn("stability metrics", page)
        self.assertIn("top risk tags", page)
        self.assertIn("skipped reasons", page)
        self.assertIn("active/customer prediction confirmation", page)
        self.assertIn("Refresh shadow replay", page)

    def test_governance_console_does_not_expose_real_prediction_or_training_buttons(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8").lower()

        self.assertNotIn(">generate customer prediction<", page)
        self.assertNotIn(">write active model<", page)
        self.assertNotIn(">run promotion<", page)
        self.assertNotIn(">train candidate<", page)


if __name__ == "__main__":
    unittest.main()
