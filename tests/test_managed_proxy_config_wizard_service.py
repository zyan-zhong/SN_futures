from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_proxy_config_wizard_service import build_managed_proxy_config_wizard


def _write_valid_templates(project: Path, *, gitignore: str | None = None) -> None:
    (project / "config").mkdir(parents=True, exist_ok=True)
    (project / ".env.example").write_text(
        "\n".join(
            [
                "SN_MANAGED_PROXY_ENABLED=false",
                "SN_MANAGED_PROXY_BASE_URL=https://managed-proxy.example",
                "SN_MANAGED_PROXY_TOKEN=your_managed_proxy_token_here",
                "SN_MANAGED_PROXY_TIMEOUT_SECONDS=20",
            ]
        ),
        encoding="utf-8",
    )
    (project / "config" / "managed_proxy.example.json").write_text(
        json.dumps(
            {
                "SN_MANAGED_PROXY_ENABLED": False,
                "SN_MANAGED_PROXY_BASE_URL": "https://managed-proxy.example",
                "SN_MANAGED_PROXY_TOKEN": "your_managed_proxy_token_here",
                "SN_MANAGED_PROXY_TIMEOUT_SECONDS": 20,
            }
        ),
        encoding="utf-8",
    )
    (project / ".gitignore").write_text(
        gitignore if gitignore is not None else ".env\n.env.local\nconfig/managed_proxy.local.json\nsecrets/\n",
        encoding="utf-8",
    )


class ManagedProxyConfigWizardServiceTest(unittest.TestCase):
    def _env(self, tmp: str, **values: str) -> patch:
        base = {
            "SN_DATA_DIR": tmp,
            "SN_INSIGHT_DATA_DIR": "",
            "SN_MANAGED_PROXY_ENABLED": "",
            "SN_MANAGED_PROXY_BASE_URL": "",
            "SN_MANAGED_PROXY_TOKEN": "",
            "SN_MANAGED_PROXY_TIMEOUT_SECONDS": "",
            "SN_MANAGED_DATA_PROXY_ENABLED": "",
            "SN_MANAGED_DATA_PROXY_URL": "",
            "SN_MANAGED_DATA_PROXY_TOKEN": "",
        }
        base.update(values)
        return patch.dict(os.environ, base, clear=False)

    def test_missing_templates_block_wizard_without_downstream_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            project = Path(tmp) / "repo"
            project.mkdir()
            (project / ".gitignore").write_text(".env\n.env.local\nconfig/managed_proxy.local.json\nsecrets/\n", encoding="utf-8")

            report = build_managed_proxy_config_wizard(project_root=project)
            report_exists = Path(report["report_path"]).exists()

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["env_var_template_status"], "missing")
        self.assertEqual(report["local_config_template_status"], "missing")
        self.assertIn("env_template_missing", report["blocking_reasons"])
        self.assertIn("local_config_template_missing", report["blocking_reasons"])
        self.assertEqual(report["next_allowed_action"], "fix_managed_proxy_config_templates")
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertTrue(report_exists)

    def test_gitignore_missing_secret_patterns_blocks_wizard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            project = Path(tmp) / "repo"
            project.mkdir()
            _write_valid_templates(project, gitignore=".env\n")

            report = build_managed_proxy_config_wizard(project_root=project)

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["env_var_template_status"], "pass")
        self.assertEqual(report["local_config_template_status"], "pass")
        self.assertIn("gitignore_secret_coverage_incomplete", report["blocking_reasons"])
        self.assertIn(".env.local", report["gitignore_secret_coverage"]["missing_patterns"])
        self.assertEqual(report["next_allowed_action"], "fix_managed_proxy_config_templates")

    def test_complete_templates_are_ready_but_do_not_make_missing_endpoint_token_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            project = Path(tmp) / "repo"
            project.mkdir()
            _write_valid_templates(project)

            report = build_managed_proxy_config_wizard(project_root=project)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["env_var_template_status"], "pass")
        self.assertEqual(report["local_config_template_status"], "pass")
        self.assertEqual(report["gitignore_secret_coverage"]["status"], "pass")
        self.assertFalse(report["endpoint_configured"])
        self.assertFalse(report["token_configured"])
        self.assertEqual(report["next_allowed_action"], "configure_managed_proxy_endpoint_or_token")
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_wizard_report_never_contains_full_configured_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_PROXY_ENABLED="true",
            SN_MANAGED_PROXY_BASE_URL="https://managed.example",
            SN_MANAGED_PROXY_TOKEN="managed-secret-token",
        ):
            project = Path(tmp) / "repo"
            project.mkdir()
            _write_valid_templates(project)
            report = build_managed_proxy_config_wizard(project_root=project)
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertTrue(report["endpoint_configured"])
        self.assertTrue(report["token_configured"])
        self.assertNotIn("managed-secret-token", serialized)
        self.assertNotIn("managed-secret-token", report_text)
        self.assertNotIn("Authorization", serialized)

    def test_setup_steps_include_safe_local_guidance_and_ordered_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            project = Path(tmp) / "repo"
            project.mkdir()
            _write_valid_templates(project)

            report = build_managed_proxy_config_wizard(project_root=project)

        steps = " ".join(report["setup_steps"])
        checklist = " ".join(report["dry_run_checklist"])
        self.assertIn("local shell", steps)
        self.assertIn("ignored", steps)
        self.assertIn("ChatGPT", steps)
        self.assertIn("logs", steps)
        self.assertIn("commits", steps)
        self.assertIn("issues", steps)
        self.assertIn("setup dry-run", steps)
        self.assertIn("health", steps)
        self.assertIn("PIT audit", steps)
        self.assertIn("masked", checklist)


if __name__ == "__main__":
    unittest.main()
