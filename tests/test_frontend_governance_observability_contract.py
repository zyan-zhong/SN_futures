from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendGovernanceObservabilityContractTest(unittest.TestCase):
    def test_frontend_exposes_observability_api_helpers_and_type(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getGovernanceObservability", terminal)
        self.assertIn("refreshGovernanceObservability", terminal)
        self.assertIn("/api/terminal/governance/observability", terminal)
        self.assertIn("/api/terminal/governance/refresh-observability", terminal)
        self.assertIn("GovernanceObservabilityPayload", types)
        self.assertIn("telemetry_summary", types)
        self.assertIn("slo_results", types)
        self.assertIn("error_budget", types)

    def test_governance_console_renders_observability_slo_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Observability / SLO", page)
        self.assertIn("SLO status", page)
        self.assertIn("safe check success rate", page)
        self.assertIn("p95 latency", page)
        self.assertIn("error budget remaining", page)
        self.assertIn("stale reports", page)
        self.assertIn("secret scan status", page)
        self.assertIn("forbidden violations", page)
        self.assertIn("Refresh observability", page)

    def test_governance_console_observability_does_not_add_high_risk_buttons(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")
        lower_page = page.lower()

        for phrase in [
            "publish active",
            "generate customer prediction",
            "train candidate",
            "build feature store",
            "save raw token",
        ]:
            self.assertNotIn(f">{phrase}<", lower_page)


if __name__ == "__main__":
    unittest.main()
