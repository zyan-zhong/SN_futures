from __future__ import annotations

import os
import sys
import tempfile
import time
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
        fake_result = {
            "status": "success",
            "steps": [
                {"step_name": "fundamentals"},
                {"step_name": "cross_market"},
                {"step_name": "event_relevance"},
                {"step_name": "online_cross_market"},
                {"step_name": "online_lme_tin"},
                {"step_name": "managed_data_proxy"},
            ],
            "active_updated": False,
            "customer_prediction_generated": False,
            "baseline_used": False,
        }
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_NEWSAPI_KEY": ""}, clear=False), patch(
            "sn_futures.api.terminal_api.run_institutional_refresh_all",
            return_value=fake_result,
        ):
            status, payload = handle_terminal_api("/api/terminal/refresh/all", "POST", {}, "{}")
            final = self._wait_for_task(str(payload["task_id"]))
        self.assertEqual(status, 200)
        result = final.get("result", {})
        steps = [step.get("step_name") for step in result.get("steps", [])]
        self.assertIn("fundamentals", steps)
        self.assertIn("cross_market", steps)
        self.assertIn("event_relevance", steps)
        self.assertIn("online_cross_market", steps)
        self.assertIn("online_lme_tin", steps)
        self.assertIn("managed_data_proxy", steps)
        self.assertNotIn("predictions", steps)
        self.assertFalse(result.get("active_updated", False))
        self.assertFalse(result.get("customer_prediction_generated", False))
        self.assertFalse(result.get("baseline_used", False))

    def _wait_for_task(self, task_id: str) -> dict:
        for _ in range(80):
            _, payload = handle_terminal_api("/api/terminal/tasks/status", "GET", query={"id": [task_id]})
            if payload.get("status") in {"success", "failed"}:
                time.sleep(0.05)
                return payload
            time.sleep(0.05)
        return {}


if __name__ == "__main__":
    unittest.main()
