from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleasePackagingTest(unittest.TestCase):
    def test_pyinstaller_spec_excludes_local_secrets_and_requires_frontend_dist(self) -> None:
        spec = (ROOT / "packaging" / "SNInsightTerminal.spec").read_text(encoding="utf-8")
        self.assertIn("frontend_dist", spec)
        self.assertIn("正式发行需要先构建 frontend/dist", spec)
        self.assertIn(".env.example", spec)
        self.assertNotIn('".env"', spec)
        self.assertIn("frontend.node_modules", spec)

    def test_inno_script_is_per_user_and_keeps_user_data(self) -> None:
        iss = (ROOT / "packaging" / "SNInsightTerminal.iss").read_text(encoding="utf-8")
        self.assertIn("PrivilegesRequired=lowest", iss)
        self.assertIn("{localappdata}\\Programs\\SNInsightTerminal", iss)
        self.assertIn("SNInsightTerminal_Setup", iss)
        files_section = iss.split("[Files]", 1)[1].split("[", 1)[0]
        install_delete_section = iss.split("[InstallDelete]", 1)[1].split("[", 1)[0]
        self.assertNotIn(".env", files_section)
        self.assertNotIn("secrets.json", files_section)
        self.assertIn('{app}\\_internal\\private\\.env', install_delete_section)
        self.assertIn('{app}\\_internal\\private\\secrets.json', install_delete_section)
        self.assertNotIn("{localappdata}\\SNInsightTerminal", install_delete_section)

    def test_build_release_script_checks_frontend_dist_and_tooling(self) -> None:
        script = (ROOT / "packaging" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn("frontend\\dist\\index.html", script)
        self.assertIn("pyinstaller packaging/SNInsightTerminal.spec", script)
        self.assertIn("ISCC", script)
        self.assertIn("SHA256SUMS.txt", script)

    def test_release_guide_exists(self) -> None:
        self.assertTrue((ROOT / "docs" / "RELEASE_GUIDE.md").exists())


if __name__ == "__main__":
    unittest.main()
