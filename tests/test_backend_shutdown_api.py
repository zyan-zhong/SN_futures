from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.process_lifecycle_service import write_server_runtime_files
from sn_futures.services.task_queue_service import is_accepting_new_tasks, resume_accepting_new_tasks


class BackendShutdownApiTest(unittest.TestCase):
    def tearDown(self) -> None:
        resume_accepting_new_tasks()

    def test_shutdown_endpoint_marks_runtime_and_stops_new_tasks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            write_server_runtime_files(host="127.0.0.1", port=8878, session_id="shutdown-api")

            status, payload = handle_terminal_api(
                "/api/terminal/system/shutdown",
                method="POST",
                body=b'{"reason":"unit-test"}',
            )
            after_status, after_payload = handle_terminal_api("/api/terminal/system/process-status")

        self.assertEqual(status, 200)
        self.assertIn(payload["status"], {"shutdown_requested", "shutdown_marked"})
        self.assertFalse(payload["accepting_new_tasks"])
        self.assertFalse(is_accepting_new_tasks())
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertEqual(after_status, 200)
        self.assertTrue(after_payload["shutdown_requested"])
        self.assertFalse(after_payload["pid_file_exists"])


if __name__ == "__main__":
    unittest.main()
