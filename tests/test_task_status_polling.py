from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


class TaskStatusPollingTest(unittest.TestCase):
    def test_status_recent_and_cancel_contract(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            start_status, task = handle_terminal_api(
                "/api/terminal/tasks/start",
                method="POST",
                body={"kind": "run_learning_scheduler", "hold_seconds": 0.2},
            )
            self.assertEqual(start_status, 200)
            task_id = str(task["task_id"])

            status_status, running = handle_terminal_api("/api/terminal/tasks/status", query={"id": [task_id]})
            self.assertEqual(status_status, 200)
            self.assertEqual(running.get("task_id"), task_id)
            self.assertIn(running.get("status"), {"queued", "running", "success"})

            recent_status, recent = handle_terminal_api("/api/terminal/tasks/recent")
            self.assertEqual(recent_status, 200)
            self.assertGreaterEqual(recent.get("count", 0), 1)

            cancel_status, cancelled = handle_terminal_api("/api/terminal/tasks/cancel", method="POST", query={"id": [task_id]})
            self.assertEqual(cancel_status, 200)
            self.assertEqual(cancelled.get("task_id"), task_id)
            self.assertIn(cancelled.get("status"), {"cancel_requested", "success"})

    def test_start_rejects_unknown_task_kind(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/tasks/start", method="POST", body={"kind": "unknown_long_task"})

        self.assertEqual(status, 400)
        self.assertEqual(payload.get("error"), "invalid_task_kind")


if __name__ == "__main__":
    unittest.main()
