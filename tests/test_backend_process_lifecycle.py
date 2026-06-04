from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.process_lifecycle_service import (
    get_process_status,
    mark_server_shutdown,
    write_server_runtime_files,
)


class BackendProcessLifecycleTest(unittest.TestCase):
    def test_server_runtime_files_are_written_and_marked_shutdown(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            runtime = write_server_runtime_files(host="127.0.0.1", port=8765, session_id="test-session")
            status = get_process_status()
            shutdown = mark_server_shutdown(reason="unit-test")
            after = get_process_status()

        self.assertTrue(runtime["pid_file_exists"])
        self.assertEqual(status["pid"], os.getpid())
        self.assertEqual(status["port"], 8765)
        self.assertEqual(status["session_id"], "test-session")
        self.assertEqual(shutdown["status"], "shutdown_marked")
        self.assertFalse(after["pid_file_exists"])
        self.assertTrue(after["stale"])

    def test_process_status_api_is_available_and_json_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            write_server_runtime_files(host="127.0.0.1", port=8877, session_id="api-test")
            status, payload = handle_terminal_api("/api/terminal/system/process-status")

        self.assertEqual(status, 200)
        self.assertEqual(payload["port"], 8877)
        self.assertTrue(payload["pid_file_exists"])


if __name__ == "__main__":
    unittest.main()
