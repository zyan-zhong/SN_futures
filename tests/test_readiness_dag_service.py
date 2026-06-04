from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.readiness_dag_service import (
    build_readiness_dag,
    run_readiness_checks_dry_run,
    write_readiness_dag_report,
)


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_ready_until_quality(output: Path) -> None:
    _write_json(output / "diagnostics" / "managed_proxy_config_wizard_report.json", {"status": "ready", "blocking_reasons": []})
    _write_json(
        output / "diagnostics" / "managed_proxy_setup_report.json",
        {"status": "ready", "endpoint_contract_status": "pass", "blocking_reasons": [], "managed_proxy_health_allowed": True},
    )
    _write_json(
        output / "diagnostics" / "managed_proxy_schema_mapping_report.json",
        {"status": "ready", "schema_mapping_ready": True, "blocking_reasons": []},
    )
    _write_json(output / "diagnostics" / "managed_proxy_health.json", {"status": "ready", "v12_allowed": True, "blocking_reasons": []})
    _write_json(output / "diagnostics" / "managed_proxy_reliability_report.json", {"status": "pass", "blocking_reasons": []})
    _write_json(
        output / "diagnostics" / "managed_pit_replay_report.json",
        {"status": "pass", "point_in_time_join_ready": True, "blocking_reasons": []},
    )


class ReadinessDagServiceTest(unittest.TestCase):
    def test_setup_blocked_skips_downstream_readiness_chain(self) -> None:
        tmp = _workspace_tmp("readiness-setup-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _write_json(output / "diagnostics" / "managed_proxy_config_wizard_report.json", {"status": "ready", "blocking_reasons": []})
            _write_json(
                output / "diagnostics" / "managed_proxy_setup_report.json",
                {
                    "status": "blocked",
                    "blocking_reasons": ["managed_proxy_token_missing"],
                    "next_allowed_action": "configure_managed_proxy_token",
                },
            )

            dag = build_readiness_dag()

        self.assertEqual(dag["status"], "blocked")
        self.assertEqual(dag["node_statuses"]["managed_proxy_setup"]["status"], "blocked")
        for node_id in ("managed_proxy_health", "managed_data_audit", "feature_store_v12", "training_dataset_v12", "candidate_v12"):
            self.assertEqual(dag["node_statuses"][node_id]["status"], "skipped")
            self.assertIn(node_id, dag["skipped_nodes"])
        self.assertEqual(dag["next_allowed_action"], "configure_managed_proxy_token")
        self.assertFalse(dag["candidate_training_allowed"])
        self.assertFalse(dag["active_publish_allowed"])
        self.assertFalse(dag["training_invoked"])

    def test_pit_replay_failure_blocks_audit_and_feature_store(self) -> None:
        tmp = _workspace_tmp("readiness-pit-fail")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _seed_ready_until_quality(output)
            _write_json(
                output / "diagnostics" / "managed_pit_replay_report.json",
                {"status": "failed", "point_in_time_join_ready": False, "blocking_reasons": ["future_row_selected"]},
            )

            dag = build_readiness_dag()

        self.assertIn("pit_replay", dag["blocked_nodes"])
        self.assertEqual(dag["node_statuses"]["managed_data_audit"]["status"], "skipped")
        self.assertEqual(dag["node_statuses"]["feature_store_v12"]["status"], "skipped")
        self.assertIn("managed_data_audit", dag["blocked_nodes"])
        self.assertIn("feature_store_v12", dag["blocked_nodes"])
        self.assertFalse(dag["node_statuses"]["managed_data_audit"]["passed"])
        self.assertFalse(dag["node_statuses"]["feature_store_v12"]["passed"])

    def test_data_quality_failure_blocks_feature_store_v12(self) -> None:
        tmp = _workspace_tmp("readiness-quality-fail")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _seed_ready_until_quality(output)
            _write_json(output / "diagnostics" / "managed_data_audit_manifest.json", {"status": "ready", "v12_allowed": True, "blocking_reasons": []})
            _write_json(
                output / "diagnostics" / "managed_data_quality_scorecard.json",
                {"status": "fail", "gate_passed": False, "blocking_reasons": ["negative_inventory"]},
            )

            dag = build_readiness_dag()

        self.assertIn("data_quality", dag["blocked_nodes"])
        self.assertEqual(dag["node_statuses"]["feature_store_v12"]["status"], "skipped")
        self.assertIn("feature_store_v12", dag["blocked_nodes"])
        self.assertFalse(dag["node_statuses"]["feature_store_v12"]["passed"])

    def test_training_dataset_blocked_blocks_candidate_and_manual_approval(self) -> None:
        tmp = _workspace_tmp("readiness-td-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            _seed_ready_until_quality(output)
            _write_json(output / "diagnostics" / "managed_data_audit_manifest.json", {"status": "ready", "v12_allowed": True, "blocking_reasons": []})
            _write_json(output / "diagnostics" / "managed_data_quality_scorecard.json", {"status": "pass", "gate_passed": True, "blocking_reasons": []})
            _write_json(
                output / "feature_store" / "v12" / "feature_store_manifest.json",
                {"status": "ready", "no_lookahead_pass": True, "point_in_time_join_ready": True, "blocking_reasons": []},
            )
            _write_json(
                output / "training_dataset_manifest_v12.json",
                {"status": "blocked", "blocked_reasons": ["leakage_check_failed"], "candidate_v12_allowed": False},
            )

            dag = build_readiness_dag()

        self.assertEqual(dag["node_statuses"]["candidate_v12"]["status"], "skipped")
        self.assertIn("candidate_v12", dag["blocked_nodes"])
        self.assertFalse(dag["manual_approval_allowed"])
        self.assertFalse(dag["active_publish_allowed"])

    def test_missing_and_skipped_nodes_are_not_passed(self) -> None:
        tmp = _workspace_tmp("readiness-missing")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            dag = write_readiness_dag_report()

        self.assertEqual(dag["status"], "blocked")
        self.assertEqual(dag["node_statuses"]["config_wizard"]["status"], "missing")
        self.assertFalse(dag["node_statuses"]["config_wizard"]["passed"])
        self.assertFalse(dag["node_statuses"]["feature_store_v12"]["passed"])
        self.assertIn("feature_store_v12", dag["skipped_nodes"])
        self.assertTrue(Path(dag["report_path"]).exists())

    def test_dry_run_runner_only_calls_safe_checks_and_never_forbidden_actions(self) -> None:
        tmp = _workspace_tmp("readiness-dry-run")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False), \
            patch("sn_futures.services.readiness_dag_service.refresh_managed_proxy_config_wizard", return_value={"status": "ready", "blocking_reasons": []}) as wizard, \
            patch("sn_futures.services.readiness_dag_service.refresh_managed_proxy_setup", return_value={"status": "blocked", "blocking_reasons": ["managed_proxy_disabled"], "next_allowed_action": "enable_managed_proxy"}) as setup, \
            patch("sn_futures.services.readiness_dag_service.check_managed_proxy_health", side_effect=AssertionError("health must be skipped")), \
            patch("sn_futures.services.feature_store_v12_service.build_feature_store_v12", side_effect=AssertionError("forbidden")), \
            patch("sn_futures.services.training_dataset_v12_service.build_training_dataset_v12", side_effect=AssertionError("forbidden")), \
            patch("sn_futures.services.candidate_v12_research_service.run_candidate_v12_research", side_effect=AssertionError("forbidden")):
            result = run_readiness_checks_dry_run()

        self.assertTrue(wizard.called)
        self.assertTrue(setup.called)
        self.assertEqual(result["status"], "blocked")
        self.assertIn("managed_proxy_health", result["skipped_nodes"])
        self.assertIn("build_feature_store_v12", result["forbidden_actions"])
        self.assertFalse(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
