from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxyReliabilityContractTest(unittest.TestCase):
    def test_frontend_api_exposes_reliability_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("getManagedProxyReliability", terminal)
        self.assertIn("runManagedProxyCanary", terminal)
        self.assertIn("/api/terminal/managed-proxy/reliability", terminal)
        self.assertIn("/api/terminal/managed-proxy/run-canary", terminal)
        self.assertIn("ManagedProxyReliabilityPayload", types)
        self.assertIn("circuit_breaker_status", types)

    def test_data_status_page_renders_reliability_guardrail(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Reliability Guardrail", page)
        self.assertIn("canary status", page)
        self.assertIn("latency", page)
        self.assertIn("error rate", page)
        self.assertIn("circuit breaker", page)
        self.assertIn("cache staleness", page)
        self.assertIn("schema drift", page)
        self.assertIn("Run canary", page)


if __name__ == "__main__":
    unittest.main()
