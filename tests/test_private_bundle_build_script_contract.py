from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class PrivateBundleBuildScriptContractTest(unittest.TestCase):
    def test_build_release_rejects_embedded_private_bundle_flags(self) -> None:
        script = Path("packaging/build_release.ps1").read_text(encoding="utf-8")
        self.assertIn("PrivateBundleKeys", script)
        self.assertIn("已禁用", script)
        self.assertIn("config\\secrets.json", script)
        self.assertNotIn("ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $PrivateBundleSeed", script)

    def test_pyinstaller_spec_never_includes_private_seed(self) -> None:
        spec = Path("packaging/SNInsightTerminal.spec").read_text(encoding="utf-8")
        self.assertNotIn("private_bundle_seed", spec)
        self.assertNotIn("\"private\"", spec)
        self.assertNotIn("datas.append", spec)

    def test_gitignore_excludes_private_key_inputs(self) -> None:
        ignore = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn("packaging/private_release_keys.json", ignore)
        self.assertIn("build/private_bundle_seed.json", ignore)
        self.assertIn("release/private_bundle_seed.json", ignore)


if __name__ == "__main__":
    unittest.main()
