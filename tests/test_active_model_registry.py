from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.model_promotion_service import get_active_model_status


class ActiveModelRegistryTest(unittest.TestCase):
    def test_no_active_model_status_is_graceful(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status = get_active_model_status()
            self.assertFalse(status["exists"])
            self.assertEqual(status["status"], "no_active")
            self.assertIn("暂无", status["message_zh"])
            self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()
