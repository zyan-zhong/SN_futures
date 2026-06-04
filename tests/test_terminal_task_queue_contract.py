from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


class TerminalTaskQueueContractTest(unittest.TestCase):
    def test_task_start_status_recent_and_cancel_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/tasks/start", method="POST", body={"kind": "perf-contract"})
            self.assertEqual(status, 200)
            task_id = payload.get("task_id")
            self.assertTrue(task_id)

            for _ in range(20):
                status_status, task_status = handle_terminal_api(
                    "/api/terminal/tasks/status",
                    query={"id": [str(task_id)]},
                )
                if task_status.get("status") in {"success", "failed"}:
                    break
                time.sleep(0.05)

            self.assertEqual(status_status, 200)
            self.assertEqual(task_status.get("task_id"), task_id)
            self.assertIn(task_status.get("status"), {"queued", "running", "success", "failed"})

            recent_status, recent = handle_terminal_api("/api/terminal/tasks/recent")
            self.assertEqual(recent_status, 200)
            self.assertGreaterEqual(recent.get("count", 0), 1)

            cancel_status, cancel = handle_terminal_api(
                "/api/terminal/tasks/cancel",
                method="POST",
                query={"id": [str(task_id)]},
            )
            self.assertEqual(cancel_status, 200)
            self.assertEqual(cancel.get("task_id"), task_id)

    def test_same_kind_task_is_deduped_while_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            first_status, first = handle_terminal_api("/api/terminal/tasks/start", method="POST", body={"kind": "same-kind", "hold_seconds": 0.2})
            second_status, second = handle_terminal_api("/api/terminal/tasks/start", method="POST", body={"kind": "same-kind", "hold_seconds": 0.2})
            for _ in range(20):
                _, current = handle_terminal_api("/api/terminal/tasks/status", query={"id": [str(first.get("task_id"))]})
                if current.get("status") in {"success", "failed"}:
                    break
                time.sleep(0.05)

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertEqual(first.get("task_id"), second.get("task_id"))
        self.assertTrue(second.get("deduped"))

    def test_same_kind_task_dedupe_respects_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            first_status, first = handle_terminal_api(
                "/api/terminal/tasks/start",
                method="POST",
                body={"kind": "same-kind", "hold_seconds": 0.05, "scope": "first"},
            )
            second_status, second = handle_terminal_api(
                "/api/terminal/tasks/start",
                method="POST",
                body={"kind": "same-kind", "hold_seconds": 0.05, "scope": "second"},
            )
            for task_id in (str(first.get("task_id")), str(second.get("task_id"))):
                for _ in range(20):
                    _, current = handle_terminal_api("/api/terminal/tasks/status", query={"id": [task_id]})
                    if current.get("status") in {"success", "failed"}:
                        break
                    time.sleep(0.05)

        self.assertEqual(first_status, 200)
        self.assertEqual(second_status, 200)
        self.assertNotEqual(first.get("task_id"), second.get("task_id"))
        self.assertFalse(second.get("deduped"))


if __name__ == "__main__":
    unittest.main()
