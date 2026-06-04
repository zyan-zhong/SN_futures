from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend" / "src"


class FrontendPostReleaseMonitoringContractTest(unittest.TestCase):
    def test_frontend_exposes_monitoring_spec_type_and_api_helpers(self) -> None:
        terminal = (FRONTEND / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (FRONTEND / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getPostReleaseMonitoringSpec", terminal)
        self.assertIn("refreshPostReleaseMonitoringSpec", terminal)
        self.assertIn("/api/terminal/governance/post-release-monitoring-spec", terminal)
        self.assertIn("/api/terminal/governance/refresh-post-release-monitoring-spec", terminal)
        self.assertIn("PostReleaseMonitoringSpecPayload", types)
        self.assertIn("monitoring_mode", types)
        self.assertIn("live_monitoring_enabled", types)
        self.assertIn("alert_thresholds", types)

    def test_governance_console_renders_post_release_monitoring_card(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8")

        self.assertIn("Post-Release Monitoring Spec", page)
        self.assertIn("monitoring mode", page)
        self.assertIn("live monitoring enabled", page)
        self.assertIn("sentinel count", page)
        self.assertIn("key alert thresholds", page)
        self.assertIn("readiness gaps", page)
        self.assertIn("shadow replay status", page)
        self.assertIn("active/customer prediction sentinel status", page)
        self.assertIn("Refresh monitoring spec", page)

    def test_governance_console_does_not_expose_monitoring_deployment_or_prediction_buttons(self) -> None:
        page = (FRONTEND / "pages" / "GovernanceConsolePage.tsx").read_text(encoding="utf-8").lower()

        self.assertNotIn(">deploy monitoring<", page)
        self.assertNotIn(">start monitoring daemon<", page)
        self.assertNotIn(">generate customer prediction<", page)
        self.assertNotIn(">write active model<", page)


if __name__ == "__main__":
    unittest.main()
