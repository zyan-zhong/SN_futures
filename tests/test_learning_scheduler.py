from __future__ import annotations

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.learning_scheduler_service import (
    REQUIRED_LEARNING_TASKS,
    get_learning_scheduler_status,
    run_learning_scheduler_once,
)


class LearningSchedulerTest(unittest.TestCase):
    def test_manual_run_executes_required_research_tasks_and_records_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            with patch("sn_futures.services.learning_scheduler_service.run_institutional_refresh_steps") as refresh, \
                patch("sn_futures.services.learning_scheduler_service.build_feature_store_v5") as feature_store, \
                patch("sn_futures.services.learning_scheduler_service.run_candidate_v5_research") as candidate, \
                patch("sn_futures.services.learning_scheduler_service.run_institutional_validation") as validation, \
                patch("sn_futures.services.learning_scheduler_service.promote_candidate") as promote, \
                patch("sn_futures.services.learning_scheduler_service.archive_research_run") as archive:
                refresh.return_value = {"status": "success"}
                feature_store.return_value = {"status": "success", "version": "v5"}
                candidate.return_value = {
                    "status": "success",
                    "candidate_version": "v5",
                    "artifact_dir": str(Path(tmp) / "outputs" / "research_runs" / "v5_run"),
                    "artifact_run_id": "v5_run",
                    "active_updated": False,
                    "customer_prediction_generated": False,
                }
                validation.return_value = {"status": "success", "passed": False}
                promote.return_value = {"status": "rejected", "dry_run": True, "active_updated": False}
                archive.return_value = {"status": "success", "run_id": "scheduler_run", "artifact_dir": str(Path(tmp) / "outputs" / "research_runs" / "scheduler_run")}

                result = run_learning_scheduler_once(force=True)

            self.assertEqual(result["status"], "success")
            self.assertFalse(result["active_updated"])
            self.assertFalse(result["customer_prediction_generated"])
            self.assertTrue(result["auto_active_disabled"])
            executed = {task["task"] for task in result["tasks"]}
            self.assertTrue(set(REQUIRED_LEARNING_TASKS).issubset(executed))
            self.assertEqual(get_learning_scheduler_status()["status"], "success")
            self.assertTrue((Path(tmp) / "outputs" / "learning_scheduler" / "learning_scheduler_status.json").exists())

    def test_terminal_api_exposes_scheduler_run_status_pause_and_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status_code, status_payload = handle_terminal_api("/api/terminal/learning-scheduler/status")
            pause_code, pause_payload = handle_terminal_api("/api/terminal/learning-scheduler/pause", method="POST", body={"reason": "test"})
            resume_code, resume_payload = handle_terminal_api("/api/terminal/learning-scheduler/resume", method="POST", body={})
            with patch(
                "sn_futures.api.terminal_api.run_learning_scheduler_once",
                return_value={"status": "success", "active_updated": False, "auto_active_disabled": True},
            ):
                run_code, run_payload = handle_terminal_api(
                    "/api/terminal/learning-scheduler/run",
                    method="POST",
                    body={"force": True, "tasks": ["daily_market_refresh", "monthly_promotion_dry_run"]},
                )
                final = self._wait_for_task(str(run_payload["task_id"]))

        self.assertEqual(status_code, 200)
        self.assertIn("auto_active_disabled", status_payload)
        self.assertEqual(pause_code, 200)
        self.assertTrue(pause_payload["paused"])
        self.assertEqual(resume_code, 200)
        self.assertFalse(resume_payload["paused"])
        self.assertEqual(run_code, 200)
        self.assertEqual(run_payload["kind"], "run_learning_scheduler")
        self.assertFalse(final.get("result", {}).get("active_updated", False))

    def _wait_for_task(self, task_id: str) -> dict:
        for _ in range(60):
            _, payload = handle_terminal_api("/api/terminal/tasks/status", "GET", query={"id": [task_id]})
            if payload.get("status") in {"success", "failed"}:
                time.sleep(0.05)
                return payload
            time.sleep(0.025)
        return {}


if __name__ == "__main__":
    unittest.main()
