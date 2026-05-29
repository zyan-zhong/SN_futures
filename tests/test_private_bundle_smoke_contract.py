from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class PrivateBundleSmokeContractTest(unittest.TestCase):
    def test_smoke_script_checks_private_bundle_keys_without_printing_values(self) -> None:
        script = Path("packaging/smoke_installed.ps1").read_text(encoding="utf-8")
        self.assertIn("ExpectPrivateBundleKeys", script)
        self.assertIn("/api/terminal/settings/key-diagnostics", script)
        self.assertIn("/api/terminal/newsapi/test", script)
        self.assertIn("scan_runtime_secrets.ps1", script)
        self.assertNotIn("SN_BUNDLE_ALPHA_VANTAGE_KEY", script)
        self.assertNotIn("SN_BUNDLE_NEWSAPI_KEY", script)


if __name__ == "__main__":
    unittest.main()
