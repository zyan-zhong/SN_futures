from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class TerminalOnlineFeatureReadinessApiTest(unittest.TestCase):
    def test_online_readiness_api_is_available_and_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/factors/online-readiness", "GET", {}, None)

        self.assertEqual(status, 200)
        self.assertFalse(payload["client_upload_required"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertFalse(payload["baseline_used"])
        self.assertIn("field_readiness", payload)

    def test_docs_include_online_readiness_endpoint(self) -> None:
        paths = {item["path"] for item in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/factors/online-readiness", paths)


if __name__ == "__main__":
    unittest.main()
