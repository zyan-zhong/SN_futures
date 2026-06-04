from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.task_notification_service import build_task_notifications  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_task(root: Path, task_id: str, payload: dict[str, object]) -> None:
    path = root / "outputs" / "tasks" / f"{task_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"task_id": task_id, **payload}, ensure_ascii=False, indent=2), encoding="utf-8")


class TaskNotificationCenterServiceTest(unittest.TestCase):
    def test_stale_failed_train_candidate_is_history_not_persistent_toast(self) -> None:
        tmp = _workspace_tmp("task-notifications-stale-failed")
        _write_task(
            tmp,
            "train_candidate-old",
            {
                "kind": "train_candidate",
                "status": "failed",
                "created_at": "2026-06-01T00:00:00",
                "finished_at": "2026-06-01T00:00:10",
                "message_zh": "training failed",
                "error_message_zh": "gate blocked",
                "progress": 100,
            },
        )

        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            payload = build_task_notifications(limit=5)

        self.assertEqual(payload["status"], "ready")
        self.assertIsNone(payload["toast_task"])
        self.assertTrue(payload["stale_failure_suppressed"])
        self.assertEqual(payload["latest_failed_task"]["kind"], "train_candidate")
        self.assertEqual(payload["latest_failed_task"]["task_id"], "train_candidate-old")
        self.assertEqual(payload["latest_failed_task"]["classification"], "research task")
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_running_task_can_be_toast_task(self) -> None:
        tmp = _workspace_tmp("task-notifications-running")
        _write_task(
            tmp,
            "refresh_market-now",
            {
                "kind": "refresh_market",
                "status": "running",
                "created_at": "2026-06-04T00:00:00",
                "started_at": "2026-06-04T00:00:01",
                "message_zh": "refreshing",
                "progress": 30,
            },
        )

        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            payload = build_task_notifications(limit=5)

        self.assertEqual(payload["toast_task"]["task_id"], "refresh_market-now")
        self.assertFalse(payload["stale_failure_suppressed"])
        self.assertEqual(payload["notification_center"]["tasks"][0]["classification"], "safe refresh task")


if __name__ == "__main__":
    unittest.main()
