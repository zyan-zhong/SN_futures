from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedDataProductionCacheGateContractTest(unittest.TestCase):
    def test_frontend_api_exposes_production_cache_gate_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ManagedDataProductionCacheGatePayload", types)
        self.assertIn("getManagedDataProductionCacheGate", terminal)
        self.assertIn("refreshManagedDataProductionCacheGate", terminal)
        self.assertIn("buildManagedDataProductionCacheDryRun", terminal)
        self.assertIn("/api/terminal/managed-proxy/production-cache-gate", terminal)
        self.assertIn("/api/terminal/managed-proxy/refresh-production-cache-gate", terminal)
        self.assertIn("/api/terminal/managed-proxy/build-production-cache-dry-run", terminal)

    def test_data_status_page_renders_gate_without_write_inputs(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Production Managed Cache Gate", page)
        self.assertIn("production_cache_write_allowed", page)
        self.assertIn("production_cache_written", page)
        self.assertIn("precondition checks", page.lower())
        self.assertIn("dry-run plan", page.lower())
        self.assertIn("human approval checklist", page.lower())
        self.assertIn("no production cache write performed", page.lower())
        self.assertNotIn('type="password"', page)
        self.assertNotIn("custom output path", page.lower())
        self.assertNotIn("raw token input", page.lower())


if __name__ == "__main__":
    unittest.main()
