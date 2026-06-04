from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_proxy_operator_runbook_service import (
    build_operator_onboarding_runbook,
    build_safe_config_verification_report,
    validate_no_raw_secret_echo,
    validate_operator_config_files,
    validate_operator_environment_aliases,
    validate_secret_storage_boundaries,
)


REQUIRED_GITIGNORE = ".env\n.env.local\nconfig/managed_proxy.local.json\nconfig/managed_proxy.mapping.local.json\nsecrets/\n"


def _write_templates(project: Path, *, env: str | None = None, local: dict[str, object] | None = None, mapping: dict[str, object] | None = None, gitignore: str | None = None) -> None:
    (project / "config").mkdir(parents=True, exist_ok=True)
    (project / ".env.example").write_text(
        env
        if env is not None
        else "\n".join(
            [
                "SN_MANAGED_PROXY_ENABLED=false",
                "SN_MANAGED_PROXY_BASE_URL=https://managed-proxy.example",
                "SN_MANAGED_PROXY_TOKEN=your_managed_proxy_token_here",
                "SN_MANAGED_PROXY_TIMEOUT_SECONDS=20",
                "SN_MANAGED_DATA_PROXY_ENABLED=false",
                "SN_MANAGED_DATA_PROXY_URL=https://managed-proxy.example",
                "SN_MANAGED_DATA_PROXY_TOKEN=your_managed_proxy_token_here",
                "SN_MANAGED_DATA_PROXY_TIMEOUT_SECONDS=20",
            ]
        ),
        encoding="utf-8",
    )
    (project / "config" / "managed_proxy.example.json").write_text(
        json.dumps(
            local
            if local is not None
            else {
                "SN_MANAGED_PROXY_ENABLED": False,
                "SN_MANAGED_PROXY_BASE_URL": "https://managed-proxy.example",
                "SN_MANAGED_PROXY_TOKEN": "your_managed_proxy_token_here",
                "SN_MANAGED_PROXY_TIMEOUT_SECONDS": 20,
                "note": "Copy to config/managed_proxy.local.json. Never commit real endpoint or token values.",
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (project / "config" / "managed_proxy.mapping.example.json").write_text(
        json.dumps(
            mapping
            if mapping is not None
            else {
                "description": "Template only. Copy to config/managed_proxy.mapping.local.json.",
                "field_mapping": {
                    "provider_source_timestamp": "source_timestamp",
                    "provider_asof_date": "asof_date",
                    "provider_ingest_timestamp": "ingest_timestamp",
                    "provider_trading_date": "trading_date",
                    "provider_prediction_cutoff_date": "prediction_cutoff_date",
                    "provider_spot_price": "spot_price",
                    "provider_spot_premium": "spot_premium",
                    "provider_spot_futures_basis": "spot_futures_basis",
                    "provider_shfe_inventory": "shfe_inventory",
                    "provider_shfe_warehouse_receipt": "shfe_warehouse_receipt",
                    "provider_lme_tin_close": "lme_tin_close",
                    "provider_lme_inventory": "lme_inventory",
                    "provider_near_contract_close": "near_contract_close",
                    "provider_near_open_interest": "near_open_interest",
                    "provider_far_contract_close": "far_contract_close",
                    "provider_far_open_interest": "far_open_interest",
                    "provider_main_contract_switch_flag": "main_contract_switch_flag",
                },
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    (project / ".gitignore").write_text(gitignore if gitignore is not None else REQUIRED_GITIGNORE, encoding="utf-8")


class ManagedProxyOperatorRunbookServiceTest(unittest.TestCase):
    def _env(self, tmp: str, **values: str) -> patch:
        base = {
            "SN_DATA_DIR": tmp,
            "SN_MANAGED_PROXY_ENABLED": "",
            "SN_MANAGED_PROXY_BASE_URL": "",
            "SN_MANAGED_PROXY_TOKEN": "",
            "SN_MANAGED_PROXY_TIMEOUT_SECONDS": "",
            "SN_MANAGED_DATA_PROXY_ENABLED": "",
            "SN_MANAGED_DATA_PROXY_URL": "",
            "SN_MANAGED_DATA_PROXY_TOKEN": "",
            "SN_MANAGED_DATA_PROXY_TIMEOUT_SECONDS": "",
        }
        base.update(values)
        return patch.dict(os.environ, base, clear=False)

    def test_missing_templates_block_operator_runbook_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            project = Path(tmp) / "repo"
            project.mkdir()
            (project / ".gitignore").write_text(REQUIRED_GITIGNORE, encoding="utf-8")

            report = build_operator_onboarding_runbook(project_root=project)

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["env_template_status"]["status"], "missing")
        self.assertEqual(report["local_config_template_status"]["status"], "missing")
        self.assertEqual(report["mapping_template_status"]["status"], "missing")
        self.assertIn("env_template_missing", report["blocking_reasons"])
        self.assertIn("local_config_template_missing", report["blocking_reasons"])
        self.assertIn("mapping_template_missing", report["blocking_reasons"])
        self.assertEqual(report["next_allowed_action"], "fix_operator_runbook_templates")
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_gitignore_secret_boundaries_require_all_local_secret_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            project = Path(tmp) / "repo"
            project.mkdir()
            _write_templates(project, gitignore=".env\n")

            boundaries = validate_secret_storage_boundaries(project_root=project)
            report = build_operator_onboarding_runbook(project_root=project)

        self.assertEqual(boundaries["status"], "blocked")
        self.assertIn("config/managed_proxy.mapping.local.json", boundaries["missing_patterns"])
        self.assertIn("secrets/", boundaries["missing_patterns"])
        self.assertIn("gitignore_secret_coverage_incomplete", report["blocking_reasons"])

    def test_valid_templates_with_missing_runtime_config_are_ready_with_missing_config_not_connected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            project = Path(tmp) / "repo"
            project.mkdir()
            _write_templates(project)

            report = build_operator_onboarding_runbook(project_root=project)

        self.assertEqual(report["status"], "ready_with_missing_config")
        self.assertEqual(report["env_template_status"]["status"], "pass")
        self.assertEqual(report["local_config_template_status"]["status"], "pass")
        self.assertEqual(report["mapping_template_status"]["status"], "pass")
        self.assertFalse(report["endpoint_configured"])
        self.assertFalse(report["token_configured"])
        self.assertEqual(report["next_allowed_action"], "configure_managed_proxy_endpoint_or_token")
        self.assertFalse(report["training_invoked"])

    def test_configured_token_is_masked_and_full_value_never_echoed(self) -> None:
        secret = "managed-secret-token-123456"
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_PROXY_ENABLED="true",
            SN_MANAGED_PROXY_BASE_URL="https://managed.example",
            SN_MANAGED_PROXY_TOKEN=secret,
        ):
            project = Path(tmp) / "repo"
            project.mkdir()
            _write_templates(project)

            report = build_operator_onboarding_runbook(project_root=project)
            verification = build_safe_config_verification_report(project_root=project)
            serialized = json.dumps({"report": report, "verification": verification}, ensure_ascii=False)
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")

        self.assertTrue(report["endpoint_configured"])
        self.assertTrue(report["token_configured"])
        self.assertTrue(report["token_masked"])
        self.assertNotEqual(report["token_masked"], secret)
        self.assertNotIn(secret, serialized)
        self.assertNotIn(secret, report_text)
        self.assertNotIn("Authorization", serialized)
        self.assertEqual(report["safe_echo_check"]["status"], "pass")

    def test_env_alias_consistency_accepts_new_and_legacy_aliases(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_PROXY_ENABLED="true",
            SN_MANAGED_DATA_PROXY_ENABLED="true",
            SN_MANAGED_PROXY_BASE_URL="https://managed.example",
            SN_MANAGED_DATA_PROXY_URL="https://managed.example",
            SN_MANAGED_PROXY_TOKEN="same-token-value",
            SN_MANAGED_DATA_PROXY_TOKEN="same-token-value",
        ):
            result = validate_operator_environment_aliases()

        self.assertEqual(result["status"], "pass")
        self.assertIn("SN_MANAGED_PROXY_TOKEN", result["aliases_checked"])
        self.assertIn("SN_MANAGED_DATA_PROXY_TOKEN", result["aliases_checked"])
        self.assertEqual(result["conflicts"], [])

    def test_env_alias_conflict_is_warning_not_secret_echo(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(
            tmp,
            SN_MANAGED_PROXY_TOKEN="new-token-value",
            SN_MANAGED_DATA_PROXY_TOKEN="legacy-token-value",
        ):
            result = validate_operator_environment_aliases()
            serialized = json.dumps(result, ensure_ascii=False)

        self.assertEqual(result["status"], "warning")
        self.assertIn("SN_MANAGED_PROXY_TOKEN/SN_MANAGED_DATA_PROXY_TOKEN", result["conflicts"])
        self.assertNotIn("new-token-value", serialized)
        self.assertNotIn("legacy-token-value", serialized)

    def test_validation_helpers_do_not_call_downstream_build_or_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp), patch(
            "sn_futures.services.feature_store_v12_service.build_feature_store_v12"
        ) as fs, patch(
            "sn_futures.services.training_dataset_v12_service.build_training_dataset_v12"
        ) as td, patch(
            "sn_futures.services.candidate_v12_research_service.run_candidate_v12_research"
        ) as candidate:
            project = Path(tmp) / "repo"
            project.mkdir()
            _write_templates(project)

            validate_operator_config_files(project_root=project)
            build_operator_onboarding_runbook(project_root=project)

        fs.assert_not_called()
        td.assert_not_called()
        candidate.assert_not_called()

    def test_validate_no_raw_secret_echo_detects_forbidden_echo(self) -> None:
        result = validate_no_raw_secret_echo({"warning_reasons": ["Authorization: Bearer managed-secret-token"]}, extra_secrets=["managed-secret-token"])

        self.assertEqual(result["status"], "blocked")
        self.assertIn("raw_secret_echo_detected", result["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
