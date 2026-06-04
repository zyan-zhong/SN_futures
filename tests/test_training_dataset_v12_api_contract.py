from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class TrainingDatasetV12ApiContractTest(unittest.TestCase):
    def test_docs_expose_training_dataset_v12_endpoints(self) -> None:
        paths = {entry["path"] for entry in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/training-dataset/v12", paths)
        self.assertIn("/api/terminal/training-dataset/build-v12", paths)

    def test_get_v12_status_uses_v12_service(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_training_dataset_v12_status",
            return_value={"status": "blocked", "dataset_version": "v12", "candidate_v12_allowed": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/training-dataset/v12", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["dataset_version"], "v12")
        self.assertFalse(payload["candidate_v12_allowed"])

    def test_direct_build_v12_uses_task_without_candidate_training(self) -> None:
        with patch("sn_futures.api.terminal_api.build_training_dataset_v12", return_value={"status": "blocked"}, create=True), patch(
            "sn_futures.api.terminal_api.start_task"
        ) as start_task:
            start_task.side_effect = lambda kind, fn=None, payload=None: {
                "task_id": "training-dataset-v12",
                "kind": kind,
                "status": "queued",
                "payload": payload or {},
            }
            status, payload = handle_terminal_api("/api/terminal/training-dataset/build-v12", method="POST", body=json.dumps({}))

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "build_training_dataset")
        self.assertEqual(payload["payload"]["dataset_version"], "v12")
        self.assertFalse(payload["payload"].get("candidate_v12_auto_triggered", True))
        self.assertFalse(payload["payload"].get("active_publish", True))

    def test_generic_build_dataset_version_v12_uses_v12_service(self) -> None:
        with patch("sn_futures.api.terminal_api.build_training_dataset_v12", return_value={"status": "blocked"}, create=True), patch(
            "sn_futures.api.terminal_api.start_task"
        ) as start_task:
            start_task.side_effect = lambda kind, fn=None, payload=None: {
                "task_id": "training-dataset-v12",
                "kind": kind,
                "status": "queued",
                "payload": payload or {},
            }
            status, payload = handle_terminal_api(
                "/api/terminal/training-dataset/build",
                method="POST",
                body=json.dumps({"dataset_version": "v12"}),
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["payload"]["dataset_version"], "v12")
        self.assertFalse(payload["payload"].get("candidate_v12_auto_triggered", True))


if __name__ == "__main__":
    unittest.main()
