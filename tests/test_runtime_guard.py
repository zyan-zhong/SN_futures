from __future__ import annotations

import sys
import tempfile
import unittest
import os
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.bootstrap.runtime_guard import BUILD_ID, SingleInstanceLock, write_runtime_state


class RuntimeGuardTest(unittest.TestCase):
    def test_single_instance_lock_blocks_second_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            lock_path = Path(tmp) / "test.lock"
            first = SingleInstanceLock(lock_path)
            second = SingleInstanceLock(lock_path)
            self.assertTrue(first.acquire())
            try:
                self.assertFalse(second.acquire())
            finally:
                first.release()

    def test_runtime_state_contains_build_id(self) -> None:
        os.environ.pop("SN_INSIGHT_DATA_DIR", None)
        state = write_runtime_state(api_port=8765, frontend_port=8765, message="test")
        self.assertEqual(state.build_id, BUILD_ID)
        self.assertGreater(state.active_pid, 0)
        self.assertTrue(state.data_dir)


if __name__ == "__main__":
    unittest.main()
