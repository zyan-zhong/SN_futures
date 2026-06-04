from __future__ import annotations

import unittest

import sys

sys.path.insert(0, "src")

from sn_futures.services.governance_access_control_service import API_ACTIONS, classify_api_action


class ManagedDataProductionCacheGateAccessControlTest(unittest.TestCase):
    def test_gate_endpoints_are_safe_report_actions(self) -> None:
        actions = {row["path"]: row for row in API_ACTIONS}

        self.assertIn("/api/terminal/managed-proxy/production-cache-gate", actions)
        self.assertIn("/api/terminal/managed-proxy/refresh-production-cache-gate", actions)
        self.assertIn("/api/terminal/managed-proxy/build-production-cache-dry-run", actions)
        self.assertEqual(classify_api_action("GET", "/api/terminal/managed-proxy/production-cache-gate")["category"], "safe_read")
        self.assertEqual(classify_api_action("POST", "/api/terminal/managed-proxy/refresh-production-cache-gate")["category"], "report_write")
        self.assertEqual(classify_api_action("POST", "/api/terminal/managed-proxy/build-production-cache-dry-run")["category"], "safe_dry_run")

    def test_actual_production_cache_write_is_not_exposed_as_api_action(self) -> None:
        paths = {row["path"] for row in API_ACTIONS}

        self.assertNotIn("/api/terminal/managed-proxy/write-production-cache", paths)
        self.assertNotIn("/api/terminal/managed-proxy/promote-production-cache", paths)


if __name__ == "__main__":
    unittest.main()
