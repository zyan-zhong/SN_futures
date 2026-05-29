from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, "src")


class PrivateBundleBuildScriptContractTest(unittest.TestCase):
    def test_build_release_supports_private_bundle_flags(self) -> None:
        script = Path("packaging/build_release.ps1").read_text(encoding="utf-8")
        self.assertIn("PrivateBundleKeys", script)
        self.assertIn("PrivateKeysFile", script)
        self.assertIn("AllowEmbeddedProviderKeys", script)
        self.assertIn("build\\private_bundle_seed.json", script)
        self.assertIn("Mask-Key", script)
        self.assertNotIn("release\\private_bundle_seed.json", script)

    def test_pyinstaller_spec_includes_private_seed_only_if_present(self) -> None:
        spec = Path("packaging/SNInsightTerminal.spec").read_text(encoding="utf-8")
        self.assertIn("build\" / \"private_bundle_seed.json", spec)
        self.assertIn("\"private\"", spec)
        self.assertIn("private_bundle_seed.exists()", spec)

    def test_gitignore_excludes_private_key_inputs(self) -> None:
        ignore = Path(".gitignore").read_text(encoding="utf-8")
        self.assertIn("packaging/private_release_keys.json", ignore)
        self.assertIn("build/private_bundle_seed.json", ignore)
        self.assertIn("release/private_bundle_seed.json", ignore)


if __name__ == "__main__":
    unittest.main()
