from __future__ import annotations

import unittest
from pathlib import Path


class TerminalPerformanceSmokeScriptTest(unittest.TestCase):
    def test_script_documents_latency_budgets_and_writes_runtime_report(self) -> None:
        script_path = Path("scripts/smoke_terminal_performance.ps1")
        self.assertTrue(script_path.exists(), "terminal performance smoke script should exist")

        script = script_path.read_text(encoding="utf-8")
        self.assertIn("/api/terminal/summary", script)
        self.assertIn("/api/terminal/system-health", script)
        self.assertIn("/api/terminal/snapshot-lite", script)
        self.assertIn("/terminal", script)
        self.assertIn("300", script)
        self.assertIn("500", script)
        self.assertIn("terminal_performance_smoke.json", script)
        self.assertIn("SNInsightTerminal\\logs", script)
        self.assertNotIn("/api/terminal/models/train-candidate", script)
        self.assertNotIn("/api/terminal/predictions/generate", script)


if __name__ == "__main__":
    unittest.main()
