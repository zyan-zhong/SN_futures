from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


ROOT = Path(__file__).resolve().parents[1]


class FrontendManagedProxyV11ContractTest(unittest.TestCase):
    def test_terminal_api_exposes_managed_proxy_v11_loop(self) -> None:
        with patch("sn_futures.api.terminal_api.run_managed_proxy_v11_real_loop") as run_loop, patch("sn_futures.api.terminal_api.start_task") as start_task:
            run_loop.return_value = {"status": "blocked", "v11_readiness": {"ready": False}, "active_updated": False}
            start_task.side_effect = lambda kind, fn=None, payload=None: {
                "task_id": "managed-proxy-v11-test",
                "kind": kind,
                "status": "queued",
                "payload": payload or {},
            }

            status, payload = handle_terminal_api(
                "/api/terminal/refresh/managed-proxy-v11",
                method="POST",
                body=json.dumps({"force": True}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "refresh_all")
        self.assertEqual(payload["payload"]["feature_store_version"], "v11")
        self.assertFalse(payload["payload"].get("active_publish", False))

    def test_frontend_exposes_feature_store_v11_managed_readiness(self) -> None:
        terminal = (ROOT / "frontend" / "src" / "api" / "terminal.ts").read_text(encoding="utf-8")
        types = (ROOT / "frontend" / "src" / "api" / "types.ts").read_text(encoding="utf-8")
        factor_page = (ROOT / "frontend" / "src" / "pages" / "FactorPage.tsx").read_text(encoding="utf-8")
        data_status = (ROOT / "frontend" / "src" / "pages" / "DataStatusPage.tsx").read_text(encoding="utf-8")

        self.assertIn("refreshManagedProxyV11", terminal)
        self.assertIn("/api/terminal/refresh/managed-proxy-v11", terminal)
        self.assertIn('getFeatureStoreStatus("v11")', factor_page)
        self.assertIn('buildFeatureStore({ version: "v11" })', factor_page)
        self.assertIn("Feature Store v11", factor_page)
        self.assertIn("feature_store_v11_readiness", types)
        self.assertIn("managed proxy v11 minimal real loop", data_status)


if __name__ == "__main__":
    unittest.main()
