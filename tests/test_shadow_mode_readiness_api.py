from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class ShadowModeReadinessApiTest(unittest.TestCase):
    def test_docs_expose_shadow_mode_readiness_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/research/shadow-mode-readiness", paths)
        self.assertIn("/api/terminal/research/refresh-shadow-mode-readiness", paths)

    def test_get_shadow_mode_readiness_does_not_generate_prediction_or_active(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_shadow_mode_readiness_spec",
            return_value={"status": "blocked", "shadow_mode_allowed": False, "active_updated": False, "customer_prediction_generated": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/research/shadow-mode-readiness", method="GET")

        self.assertEqual(status, 200)
        self.assertFalse(payload["shadow_mode_allowed"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_refresh_shadow_mode_readiness_is_report_only(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.build_shadow_mode_readiness_spec",
            return_value={"status": "blocked", "shadow_mode_allowed": False, "active_updated": False, "customer_prediction_generated": False},
            create=True,
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/research/refresh-shadow-mode-readiness",
                method="POST",
                body=json.dumps({}),
            )

        self.assertEqual(status, 200)
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
