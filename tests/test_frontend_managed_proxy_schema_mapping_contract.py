from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxySchemaMappingContractTest(unittest.TestCase):
    def test_frontend_api_exposes_schema_mapping_helpers(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")

        self.assertIn("ManagedProxySchemaMappingPayload", types)
        self.assertIn("getManagedProxySchemaMapping", terminal)
        self.assertIn("refreshManagedProxySchemaMapping", terminal)
        self.assertIn("/api/terminal/managed-proxy/schema-mapping", terminal)
        self.assertIn("/api/terminal/managed-proxy/refresh-schema-mapping", terminal)

    def test_data_status_page_renders_schema_mapping_without_raw_token_input(self) -> None:
        page = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("Managed Proxy Schema Mapping", page)
        self.assertIn("mapping status", page)
        self.assertIn("mapped fields count", page)
        self.assertIn("unmapped required fields", page)
        self.assertIn("ambiguous mappings", page)
        self.assertIn("duplicate targets", page)
        self.assertIn("mapping ready", page)
        self.assertNotIn('type="password"', page)
        self.assertNotIn("raw token", page.lower())


if __name__ == "__main__":
    unittest.main()
