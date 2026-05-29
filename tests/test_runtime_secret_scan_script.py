from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class RuntimeSecretScanScriptTest(unittest.TestCase):
    def test_scan_runtime_secrets_script_exists_and_skips_config_content(self) -> None:
        script = Path("scripts/scan_runtime_secrets.ps1").read_text(encoding="utf-8")
        self.assertIn("runtime_secret_scan.json", script)
        self.assertIn("config_file_present", script)
        self.assertIn("secrets\\.json", script)
        self.assertIn("SN_NEWSAPI_KEY", script)
        self.assertIn("X-Api-Key", script)


if __name__ == "__main__":
    unittest.main()
