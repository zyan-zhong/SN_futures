from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api
from sn_futures.services.api_response_cache import clear_api_response_cache


class SnapshotLiteContractTest(unittest.TestCase):
    def setUp(self) -> None:
        clear_api_response_cache()

    def test_snapshot_lite_endpoint_returns_only_connection_payload(self) -> None:
        status, payload = handle_terminal_api("/api/terminal/snapshot-lite")

        self.assertEqual(status, 200)
        self.assertEqual(payload.get("snapshot_mode"), "lite")
        self.assertIn("summary", payload)
        self.assertIn("refresh_status", payload)
        self.assertIn("generated_at", payload)
        self.assertIn("cache_age_seconds", payload)
        self.assertFalse(payload.get("customer_prediction_generated", True))
        self.assertNotIn("predictions", payload)
        self.assertNotIn("backtest_diagnostics", payload)
        self.assertNotIn("data_status", payload)

    def test_snapshot_lite_is_documented_as_first_screen_api(self) -> None:
        paths = {str(endpoint.get("path")) for endpoint in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/snapshot-lite", paths)

    def test_legacy_snapshot_is_cached_heavy_payload(self) -> None:
        lite_status, lite_payload = handle_terminal_api("/api/terminal/snapshot-lite")
        legacy_status, legacy_payload = handle_terminal_api("/api/terminal/snapshot")

        self.assertEqual(lite_status, 200)
        self.assertEqual(legacy_status, 200)
        self.assertEqual(lite_payload.get("snapshot_mode"), "lite")
        self.assertEqual(legacy_payload.get("snapshot_mode"), "heavy_cached")
        self.assertIn("predictions", legacy_payload)
        self.assertIn("data_status", legacy_payload)


if __name__ == "__main__":
    unittest.main()
