from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


class LongTaskAsyncApiTest(unittest.TestCase):
    def test_refresh_market_starts_task_without_blocking_http(self) -> None:
        def slow_refresh(*args, **kwargs):
            time.sleep(0.2)
            return {"status": "success", "steps": [{"step_name": "market", "status": "success"}]}

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            with patch("sn_futures.api.terminal_api.run_institutional_refresh_steps", side_effect=slow_refresh):
                started = time.perf_counter()
                status, payload = handle_terminal_api("/api/terminal/refresh/market", method="POST", body={"force": True})
                duration = time.perf_counter() - started

            self.assertEqual(status, 200)
            self.assertLess(duration, 0.1)
            self.assertEqual(payload.get("kind"), "refresh_market")
            self.assertIn(payload.get("status"), {"queued", "running"})
            self.assertIn("task_id", payload)
            self.assertNotIn("steps", payload)
            self._wait_for_task(str(payload["task_id"]))

    def test_candidate_training_starts_task_without_blocking_http(self) -> None:
        def slow_training(*args, **kwargs):
            time.sleep(0.2)
            return {"candidate_version": "v-test", "candidate_is_active": False}

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            with patch("sn_futures.api.terminal_api.run_candidate_training", side_effect=slow_training):
                started = time.perf_counter()
                status, payload = handle_terminal_api(
                    "/api/terminal/models/train-candidate",
                    method="POST",
                    body={"candidate_version": "v-test"},
                )
                duration = time.perf_counter() - started

            self.assertEqual(status, 200)
            self.assertLess(duration, 0.1)
            self.assertEqual(payload.get("kind"), "train_candidate")
            self.assertIn("task_id", payload)
            self.assertNotIn("candidate_is_active", payload)
            self._wait_for_task(str(payload["task_id"]))

    def test_validation_and_research_backtest_are_async_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            validation_status, validation = handle_terminal_api(
                "/api/terminal/validation/run-institutional-check",
                method="POST",
                body={"candidate_version": "v5", "dry_run": True},
            )
            backtest_status, backtest = handle_terminal_api(
                "/api/terminal/research/run-backtest",
                method="POST",
                body={"candidate_version": "v5", "horizons": ["1d"]},
            )

            self.assertEqual(validation_status, 200)
            self.assertEqual(validation.get("kind"), "run_validation")
            self.assertIn("task_id", validation)
            self.assertEqual(backtest_status, 200)
            self.assertEqual(backtest.get("kind"), "run_research_backtest")
            self.assertIn("task_id", backtest)
            self._wait_for_task(str(validation["task_id"]))
            self._wait_for_task(str(backtest["task_id"]))

    def _wait_for_task(self, task_id: str) -> dict:
        for _ in range(40):
            status, payload = handle_terminal_api("/api/terminal/tasks/status", query={"id": [task_id]})
            if status == 200 and payload.get("status") in {"success", "failed"}:
                time.sleep(0.1)
                return payload
            time.sleep(0.025)
        return handle_terminal_api("/api/terminal/tasks/status", query={"id": [task_id]})[1]


if __name__ == "__main__":
    unittest.main()
