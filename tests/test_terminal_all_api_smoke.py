from __future__ import annotations

import json
import os
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.all_api_smoke_service import run_all_terminal_api_smoke


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _workspace_data_dir() -> Iterator[str]:
    base = ROOT / "app_data" / "test_tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"terminal_all_api_smoke_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


class TerminalAllApiSmokeTest(unittest.TestCase):
    def test_all_key_terminal_apis_return_json_safe_payloads(self) -> None:
        with _workspace_data_dir() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            report = run_all_terminal_api_smoke()
            json.dumps(report, ensure_ascii=False, allow_nan=False)

        self.assertEqual(report["status"], "success")
        self.assertGreaterEqual(report["checked_count"], 10)
        self.assertFalse(report["secret_leak_detected"])
        self.assertTrue(report["output_path"].endswith("all_api_smoke.json"))
        for item in report["endpoints"]:
            self.assertIn("status_code", item)
            self.assertNotIn("Traceback", json.dumps(item, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
