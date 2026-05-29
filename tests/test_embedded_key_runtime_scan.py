from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class EmbeddedKeyRuntimeScanTest(unittest.TestCase):
    def test_runtime_secret_scan_fails_on_exact_runtime_leak(self) -> None:
        if not sys.platform.startswith("win"):
            self.skipTest("PowerShell runtime secret scanner is Windows-specific.")
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            leak_dir = root / "SNInsightTerminal" / "logs"
            leak_dir.mkdir(parents=True)
            (leak_dir / "leak.log").write_text("request apiKey=REALISTICLEAK1234567890", encoding="utf-8")

            completed = subprocess.run(
                [
                    "powershell",
                    "-NoProfile",
                    "-ExecutionPolicy",
                    "Bypass",
                    "-File",
                    "scripts/scan_runtime_secrets.ps1",
                    "-Root",
                    str(root),
                ],
                cwd=Path.cwd(),
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
            )

        self.assertNotEqual(completed.returncode, 0)
        self.assertIn("Possible secret findings", completed.stdout)


if __name__ == "__main__":
    unittest.main()
