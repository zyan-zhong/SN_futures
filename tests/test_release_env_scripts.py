from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class ReleaseEnvironmentScriptsTest(unittest.TestCase):
    def test_diagnose_release_env_script_exists(self) -> None:
        self.assertTrue((ROOT / "packaging" / "diagnose_release_env.ps1").exists())

    def test_build_release_has_tool_override_parameters(self) -> None:
        script = (ROOT / "packaging" / "build_release.ps1").read_text(encoding="utf-8")
        for token in ("UseExistingFrontendDist", "NodePath", "NpmPath", "SkipInstaller", "SkipSmoke", "Version"):
            self.assertIn(token, script)

    def test_build_release_does_not_delete_old_release_by_default(self) -> None:
        script = (ROOT / "packaging" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn("CleanRelease", script)
        self.assertNotIn('if (Test-Path $ReleaseDir) { Remove-Item -Recurse -Force $ReleaseDir }', script)

    def test_release_diagnosis_docs_exist(self) -> None:
        self.assertTrue((ROOT / "docs" / "RELEASE_ENV_DIAGNOSIS.md").exists())
        self.assertTrue((ROOT / "docs" / "RELEASE_ARTIFACTS.md").exists())

    def test_release_artifacts_marks_existing_setup_as_old(self) -> None:
        doc = (ROOT / "docs" / "RELEASE_ARTIFACTS.md").read_text(encoding="utf-8")
        self.assertIn("旧包，不是 Prompt 15 或 Prompt 16 新构建产物", doc)
        self.assertIn("不能把该旧包当作本轮新版本成功产物", doc)

    def test_build_release_requires_frontend_dist_for_release(self) -> None:
        script = (ROOT / "packaging" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn("frontend\\dist\\index.html", script)
        self.assertIn("frontend/dist/index.html 不存在", script)

    def test_build_release_checks_npm_cmd_and_iscc(self) -> None:
        script = (ROOT / "packaging" / "build_release.ps1").read_text(encoding="utf-8")
        self.assertIn("npm.cmd", script)
        self.assertIn("Resolve-ISCC", script)
        self.assertIn("ISCC.exe", script)

    def test_diagnosis_script_checks_common_node_paths(self) -> None:
        script = (ROOT / "packaging" / "diagnose_release_env.ps1").read_text(encoding="utf-8")
        self.assertIn("where.exe node", script)
        self.assertIn("Get-Command npm.cmd", script)
        self.assertIn("tools\\node\\node.exe", script)
        self.assertIn("python -m PyInstaller --version", script)


if __name__ == "__main__":
    unittest.main()
