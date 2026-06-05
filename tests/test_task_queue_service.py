from __future__ import annotations

import os
import importlib
import json
import sqlite3
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

import sn_futures.services.task_queue_service as task_queue_service
from sn_futures.services.task_queue_service import get_recent_tasks, get_task_status, start_task


class TaskQueueServiceTest(unittest.TestCase):
    def test_start_task_returns_immediately_writes_status_and_sanitizes_logs(self) -> None:
        def slow_failure() -> None:
            time.sleep(0.15)
            raise RuntimeError("remote error apikey=SECRET123456789")

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            started = time.perf_counter()
            task = start_task("refresh_market", slow_failure, payload={"force": True})
            duration = time.perf_counter() - started

            self.assertLess(duration, 0.1)
            self.assertEqual(task.get("kind"), "refresh_market")
            self.assertIn(task.get("status"), {"queued", "running"})
            self.assertTrue(task.get("task_id"))

            final = self._wait_for_terminal_status(str(task["task_id"]))
            self.assertEqual(final.get("status"), "failed")
            self.assertNotIn("SECRET123456789", str(final))
            self.assertIn("***", str(final))

    def test_same_kind_task_is_deduped_while_running(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            first = start_task("refresh_all_dedupe_contract", payload={"hold_seconds": 0.2})
            second = start_task("refresh_all_dedupe_contract", payload={"hold_seconds": 0.2})

            self.assertEqual(first.get("task_id"), second.get("task_id"))
            self.assertTrue(second.get("deduped"))
            self._wait_for_terminal_status(str(first["task_id"]))

    def test_recent_tasks_are_persisted_under_outputs_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            task = start_task("build_feature_store", payload={"hold_seconds": 0.01})
            self._wait_for_terminal_status(str(task["task_id"]))
            recent = get_recent_tasks()

            self.assertGreaterEqual(recent.get("count", 0), 1)
            self.assertTrue((os.path.join(tmp, "outputs", "tasks", f"{task['task_id']}.json")))
            self.assertTrue(any(item.get("kind") == "build_feature_store" for item in recent["tasks"]))

    def test_start_task_writes_queued_sqlite_row(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            task = start_task("run_learning_scheduler", payload={"hold_seconds": 0.2})
            row = self._sqlite_task_row(tmp, str(task["task_id"]))

        self.assertEqual(row["task_id"], task["task_id"])
        self.assertEqual(row["kind"], "run_learning_scheduler")
        self.assertIn(row["status"], {"queued", "running", "success"})
        self.assertEqual(row["payload_json"], '{"hold_seconds": 0.2}')

    def test_task_success_and_failure_are_persisted_in_sqlite(self) -> None:
        def succeeds() -> dict[str, str]:
            return {"status": "ok", "api_key": "SECRET123456789"}

        def fails() -> None:
            raise RuntimeError("Authorization: Bearer SECRET123456789")

        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            success = start_task("manual", succeeds)
            failure = start_task("build_feature_store", fails)

            success_row = self._sqlite_task_row(tmp, str(success["task_id"]))
            failure_row = self._sqlite_task_row(tmp, str(failure["task_id"]))

        self.assertEqual(success_row["status"], "success")
        self.assertNotIn("SECRET123456789", success_row["result_json"])
        self.assertNotEqual(json.loads(success_row["result_json"]).get("api_key"), "SECRET123456789")
        self.assertEqual(failure_row["status"], "failed")
        self.assertNotIn("SECRET123456789", failure_row["error_message"])
        self.assertIn("***", failure_row["error_message"])

    def test_cancel_requested_is_persisted_in_sqlite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            task = start_task("run_learning_scheduler", payload={"hold_seconds": 0.2})
            cancelled = task_queue_service.cancel_task(str(task["task_id"]))
            row = self._sqlite_task_row(tmp, str(task["task_id"]))

        self.assertEqual(cancelled.get("task_id"), task["task_id"])
        self.assertEqual(row["cancel_requested"], 1)
        self.assertIn(row["status"], {"cancel_requested", "success"})

    def test_recent_tasks_survive_process_restart(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            task = start_task("build_feature_store", payload={"hold_seconds": 0.01})
            self._wait_for_terminal_status(str(task["task_id"]))

            reloaded = importlib.reload(task_queue_service)
            recent = reloaded.get_recent_tasks()

        self.assertTrue(any(item.get("task_id") == task["task_id"] for item in recent["tasks"]))

    def _sqlite_task_row(self, root: str, task_id: str) -> dict:
        path = Path(root) / "outputs" / "tasks" / "task_queue.sqlite"
        self.assertTrue(path.exists(), f"missing SQLite task queue: {path}")
        with sqlite3.connect(path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute("select * from tasks where task_id = ?", (task_id,)).fetchone()
        self.assertIsNotNone(row)
        return dict(row)

    def _wait_for_terminal_status(self, task_id: str) -> dict:
        for _ in range(40):
            current = get_task_status(task_id)
            if current.get("status") in {"success", "failed", "cancel_requested"}:
                return current
            time.sleep(0.025)
        return get_task_status(task_id)


if __name__ == "__main__":
    unittest.main()
