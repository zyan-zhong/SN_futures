from __future__ import annotations

import json
import unittest
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import TERMINAL_API_DOCS, handle_terminal_api


class FeatureStoreV12ApiContractTest(unittest.TestCase):
    def test_docs_expose_direct_v12_feature_store_endpoints(self) -> None:
        paths = {row["path"] for row in TERMINAL_API_DOCS["endpoints"]}

        self.assertIn("/api/terminal/feature-store/v12", paths)
        self.assertIn("/api/terminal/feature-store/build-v12", paths)

    def test_get_feature_store_v12_returns_v12_status(self) -> None:
        with patch(
            "sn_futures.api.terminal_api.get_feature_store_v12_status",
            return_value={"status": "blocked", "feature_store_version": "v12", "training_dataset_v12_allowed": False},
            create=True,
        ):
            status, payload = handle_terminal_api("/api/terminal/feature-store/v12", method="GET")

        self.assertEqual(status, 200)
        self.assertEqual(payload["feature_store_version"], "v12")
        self.assertFalse(payload["training_dataset_v12_allowed"])

    def test_post_build_v12_uses_v12_service_task(self) -> None:
        with patch("sn_futures.api.terminal_api.build_feature_store_v12", return_value={"status": "blocked"}, create=True), patch(
            "sn_futures.api.terminal_api.start_task"
        ) as start_task:
            start_task.side_effect = lambda kind, fn=None, payload=None: {
                "task_id": "feature-store-v12",
                "kind": kind,
                "status": "queued",
                "payload": payload or {},
            }

            status, payload = handle_terminal_api("/api/terminal/feature-store/build-v12", method="POST", body=json.dumps({}))

        self.assertEqual(status, 200)
        self.assertEqual(payload["kind"], "build_feature_store")
        self.assertEqual(payload["payload"]["version"], "v12")
        self.assertFalse(payload["payload"].get("active_publish", False))
        self.assertFalse(payload["payload"].get("training_dataset_v12_auto_triggered", True))


if __name__ == "__main__":
    unittest.main()
