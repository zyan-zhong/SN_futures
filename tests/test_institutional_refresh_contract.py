from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class InstitutionalRefreshContractTest(unittest.TestCase):
    def test_docs_include_institutional_refresh_apis(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}
        self.assertIn("/api/terminal/refresh/fundamentals", paths)
        self.assertIn("/api/terminal/refresh/cross-market", paths)

    def test_refresh_all_attempts_institutional_steps_without_active_prediction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": ""}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/refresh/all", "POST", {}, "{}")
        self.assertEqual(status, 200)
        steps = [step.get("step_name") for step in payload.get("steps", [])]
        self.assertIn("fundamentals", steps)
        self.assertIn("cross_market", steps)
        self.assertIn("event_relevance", steps)
        self.assertIn("online_cross_market", steps)
        self.assertIn("online_lme_tin", steps)
        self.assertIn("managed_data_proxy", steps)
        self.assertNotIn("predictions", steps)
        self.assertFalse(payload.get("active_updated", False))
        self.assertFalse(payload.get("customer_prediction_generated", False))
        self.assertFalse(payload.get("baseline_used", False))


if __name__ == "__main__":
    unittest.main()
