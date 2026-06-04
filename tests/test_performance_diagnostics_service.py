from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.performance_diagnostics_service import run_api_performance_diagnostics
from sn_futures.api.terminal_api import handle_terminal_api


class PerformanceDiagnosticsServiceTest(unittest.TestCase):
    def test_diagnostics_times_core_terminal_apis_and_writes_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            report = run_api_performance_diagnostics()
            report_path = Path(tmp) / "outputs" / "performance" / "api_performance_report.json"
            self.assertTrue(report_path.exists())

        self.assertIn("endpoints", report)
        self.assertGreaterEqual(len(report["endpoints"]), 5)
        first = report["endpoints"][0]
        self.assertIn("endpoint", first)
        self.assertIn("duration_ms", first)
        self.assertIn("cache_hit", first)
        self.assertIn("recommended_fix", first)

    def test_performance_diagnostics_api_is_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            status, payload = handle_terminal_api("/api/terminal/performance/diagnostics")

        self.assertEqual(status, 200)
        self.assertIn("endpoints", payload)


if __name__ == "__main__":
    unittest.main()
