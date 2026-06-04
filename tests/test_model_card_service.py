from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.model_card_service import (
    build_model_card_payload,
    build_risk_disclosure,
    get_latest_model_card,
    validate_model_card_completeness,
    validate_model_card_no_secrets,
    write_model_card,
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


def _seed_blocked_research_evidence(output: Path) -> None:
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {
            "status": "blocked",
            "generated_at": "2026-06-03T12:00:00",
            "current_research_state": "managed_data_blocked",
            "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
            "blocking_reasons": ["managed_proxy_disabled", "cost_attribution:year_specific_cost_drag"],
            "top_blocking_reasons": ["managed_proxy_disabled", "cost_attribution:year_specific_cost_drag"],
            "manual_approval_recommended": False,
            "active_publish_allowed": False,
            "managed_proxy_summary": {
                "status": "blocked",
                "enabled": False,
                "configured": False,
                "setup_status": "blocked",
                "provider_status": "disabled",
                "blocking_reasons": ["managed_proxy_disabled"],
            },
            "feature_store_v12_summary": {"status": "blocked", "blocking_reasons": ["managed_data_blocked"]},
            "training_dataset_v12_summary": {"status": "blocked", "blocking_reasons": ["feature_store_v12_blocked"]},
            "candidate_v10_summary": {
                "status": "research_only",
                "year_evidence_status": "pass",
                "year_evidence_pass": True,
                "cost_attribution_status": "fail",
                "cost_attribution_pass": False,
                "main_cost_failure_drivers": ["institutional_2x_cost_negative", "year_specific_cost_drag"],
                "worst_horizon": "1d",
                "worst_regime": "high_volatility",
                "worst_year": 2022,
                "manual_approval_recommended": False,
            },
            "candidate_v12_summary": {"status": "blocked", "skipped_reasons": ["training_dataset_v12_blocked"]},
            "shadow_replay_summary": {
                "status": "research_only",
                "reason": "shadow replay is research-only evidence and does not grant active publishing.",
            },
            "post_release_monitoring_summary": {
                "status": "planning_only",
                "monitoring_mode": "planning_only",
                "live_monitoring_enabled": False,
            },
            "rollback_rehearsal_summary": {
                "status": "ready",
                "quarantine_needed": False,
                "reason": "rollback rehearsal is simulation-only evidence and does not grant active publishing.",
            },
            "manual_approval_summary": {"status": "blocked_by_gates", "approval_request_allowed": False},
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "model_research" / "evidence_bundle_index.json",
        {
            "status": "blocked",
            "generated_at": "2026-06-03T12:00:01",
            "bundle_version": "evidence_bundle_v1",
            "missing_reports": [],
            "incomplete_reports": [],
            "evidence_file_count": 7,
            "no_active_confirmation": {"confirmed": True},
            "no_prediction_confirmation": {"confirmed": True},
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "diagnostics" / "managed_proxy_setup_report.json",
        {
            "status": "blocked",
            "endpoint_configured": False,
            "token_configured": False,
            "blocking_reasons": ["managed_proxy_disabled"],
            "next_allowed_action": "configure_managed_proxy_endpoint_or_token",
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )
    _write_json(
        output / "diagnostics" / "managed_proxy_schema_mapping_report.json",
        {"status": "blocked", "schema_mapping_ready": False, "blocking_reasons": ["schema_mapping_not_run"]},
    )
    _write_json(
        output / "diagnostics" / "managed_pit_replay_report.json",
        {"status": "blocked", "point_in_time_join_ready": False, "blocking_reasons": ["no_managed_rows"]},
    )
    _write_json(
        output / "diagnostics" / "managed_data_quality_scorecard.json",
        {"status": "blocked", "gate_passed": False, "blocking_reasons": ["empty_rows"]},
    )
    _write_json(
        output / "feature_store" / "v12" / "feature_store_manifest.json",
        {"status": "blocked", "no_lookahead_pass": False, "blocking_reasons": ["managed_data_blocked"]},
    )
    _write_json(
        output / "training_dataset_manifest_v12.json",
        {"status": "blocked", "leakage_check_pass": False, "blocking_reasons": ["feature_store_v12_blocked"]},
    )
    _write_json(
        output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json",
        {
            "status": "research_only",
            "candidate_version": "v10",
            "manual_approval_recommended": False,
            "year_concentration_evidence": {"status": "pass", "passed": True},
            "cost_stress_attribution": {"status": "fail", "passed": False},
        },
    )
    _write_json(
        output / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json",
        {"status": "blocked", "candidate_version": "v12", "skipped_reasons": ["training_dataset_v12_blocked"]},
    )
    _write_json(
        output / "model_research" / "year_concentration_evidence.json",
        {"status": "pass", "passed": True, "candidate_version": "v10"},
    )
    _write_json(
        output / "model_research" / "cost_stress_attribution.json",
        {
            "status": "fail",
            "passed": False,
            "candidate_version": "v10",
            "failure_drivers": ["institutional_2x_cost_negative", "year_specific_cost_drag"],
            "by_horizon": {"rows": [{"horizon": "1d", "net_expectancy_3x": -0.12}]},
            "by_regime": {"rows": [{"regime_label": "high_volatility", "net_expectancy_3x": -0.08}]},
            "by_year": {"rows": [{"year": 2022, "net_expectancy_3x": -0.2}]},
        },
    )
    _write_json(
        output / "model_research" / "shadow_replay_report.json",
        {"status": "research_only", "customer_prediction_generated": False, "customer_visible": False},
    )
    _write_json(
        output / "model_research" / "post_release_monitoring_spec_report.json",
        {"status": "planning_only", "monitoring_mode": "planning_only", "live_monitoring_enabled": False},
    )
    _write_json(
        output / "model_research" / "rollback_rehearsal_report.json",
        {"status": "ready", "quarantine_needed": False, "active_publish_allowed": False},
    )
    _write_json(
        output / "model_research" / "manual_approval_report.json",
        {"status": "blocked_by_gates", "approval_request_allowed": False, "active_write_allowed": False},
    )
    _write_json(
        output / "model_research" / "model_registry_safety_report.json",
        {"status": "blocked", "active_write_allowed": False, "rollback_target_available": False},
    )
    _write_json(
        output / "model_research" / "production_cutover_checklist_report.json",
        {"status": "blocked", "cutover_allowed": False, "active_publish_allowed": False},
    )


class ModelCardServiceTest(unittest.TestCase):
    def test_missing_core_evidence_marks_model_card_incomplete_without_side_effects(self) -> None:
        tmp = _workspace_tmp("model-card-missing")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            payload = write_model_card()

        self.assertEqual(payload["status"], "incomplete")
        self.assertIn("research_decision_board", payload["missing_reports"])
        self.assertIn("evidence_bundle", payload["missing_reports"])
        self.assertIn("cost_stress_attribution", payload["missing_reports"])
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertTrue(payload["no_active_confirmation"]["confirmed"])
        self.assertTrue(payload["no_prediction_confirmation"]["confirmed"])

    def test_blocked_research_model_card_is_not_production_ready_or_customer_prediction(self) -> None:
        tmp = _workspace_tmp("model-card-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_blocked_research_evidence(output)
            payload = write_model_card()
            latest = get_latest_model_card()

        self.assertEqual(payload["current_status"], "managed_data_blocked / research_only")
        self.assertEqual(payload["intended_use"][0], "research_only")
        self.assertIn("production trading", payload["prohibited_use"])
        self.assertIn("customer prediction", payload["prohibited_use"])
        self.assertFalse(payload["active_model_status"]["exists"])
        self.assertFalse(payload["customer_prediction_status"]["exists"])
        self.assertEqual(payload["candidate_status"]["candidate_v10"]["scope"], "research_only")
        self.assertFalse(payload["candidate_status"]["candidate_v10"]["production_ready"])
        self.assertEqual(payload["candidate_status"]["candidate_v12"]["status"], "blocked")
        self.assertEqual(payload["shadow_replay_summary"]["mode"], "research_only")
        self.assertFalse(payload["shadow_replay_summary"]["customer_prediction"])
        self.assertEqual(payload["monitoring_spec_summary"]["mode"], "planning_only")
        self.assertFalse(payload["monitoring_spec_summary"]["deployed_monitoring"])
        self.assertFalse(payload["rollback_rehearsal_summary"]["grants_production_readiness"])
        self.assertFalse(payload["manual_approval_summary"]["manual_approval_recommended"])
        self.assertFalse(payload["manual_approval_summary"]["active_publish_allowed"])
        self.assertEqual(payload["cost_attribution_summary"]["status"], "fail")
        self.assertEqual(payload["cost_attribution_summary"]["worst_horizon"], "1d")
        self.assertEqual(payload["cost_attribution_summary"]["worst_regime"], "high_volatility")
        self.assertEqual(payload["cost_attribution_summary"]["worst_year"], 2022)
        self.assertEqual(latest["report_path"], payload["report_path"])

    def test_model_card_writes_json_markdown_and_risk_disclosure_sections(self) -> None:
        tmp = _workspace_tmp("model-card-files")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_blocked_research_evidence(output)
            payload = write_model_card()
            model_card_md = Path(payload["model_card_md_path"]).read_text(encoding="utf-8")
            risk_md = Path(payload["risk_disclosure_path"]).read_text(encoding="utf-8")

        self.assertTrue(Path(payload["report_path"]).exists())
        self.assertTrue(Path(payload["model_card_md_path"]).exists())
        self.assertTrue(Path(payload["risk_disclosure_path"]).exists())
        for section in (
            "Current Status",
            "Intended Use",
            "Prohibited Use",
            "Data Readiness",
            "Candidate Summary",
            "Validation Summary",
            "Risk Disclosure",
            "Gate Failures",
            "Evidence Paths",
            "No-Active / No-Prediction Confirmation",
            "Next Allowed Action",
        ):
            self.assertIn(section, model_card_md)
        for section in (
            "Data readiness risks",
            "PIT / no-lookahead risks",
            "Managed proxy / schema mapping risks",
            "Cost robustness risks",
            "Backtest overfitting / CPCV / PBO limitations",
            "Shadow replay limitations",
            "Monitoring limitations",
            "Approval / release limitations",
            "Operational safety limitations",
            "Current blockers",
        ):
            self.assertIn(section, risk_md)

    def test_model_card_omits_secrets_raw_managed_rows_oof_rows_and_customer_predictions(self) -> None:
        tmp = _workspace_tmp("model-card-secret")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_blocked_research_evidence(output)
            _write_json(
                output / "diagnostics" / "managed_proxy_setup_report.json",
                {
                    "status": "blocked",
                    "Authorization": "Bearer raw-secret-token-should-not-appear",
                    "endpoint_url": "https://secret.example.com/private?token=raw-secret",
                    "raw_rows": [{"spot_price": 123, "source_timestamp": "2026-06-03"}],
                    "oof_rows": [{"signal": 1, "confidence": 0.99}],
                    "customer_predictions": [{"signal": 1}],
                    "blocking_reasons": ["managed_proxy_disabled"],
                },
            )
            payload = write_model_card()
            secret_check = validate_model_card_no_secrets(payload)
            serialized = json.dumps(payload, ensure_ascii=False)

        self.assertEqual(secret_check["status"], "pass")
        self.assertNotIn("raw-secret-token-should-not-appear", serialized)
        self.assertNotIn("https://secret.example.com", serialized)
        self.assertNotIn("spot_price\": 123", serialized)
        self.assertNotIn("confidence\": 0.99", serialized)
        self.assertNotIn("customer_predictions", serialized)
        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])

    def test_completeness_requires_decision_board_evidence_bundle_cost_and_data_readiness(self) -> None:
        payload = {
            "source_status": {
                "research_decision_board": {"exists": True, "status": "blocked"},
                "evidence_bundle": {"exists": True, "status": "blocked"},
                "cost_stress_attribution": {"exists": False, "status": "missing"},
                "managed_proxy_setup": {"exists": False, "status": "missing"},
            }
        }

        completeness = validate_model_card_completeness(payload)

        self.assertEqual(completeness["status"], "incomplete")
        self.assertIn("cost_stress_attribution", completeness["missing_reports"])
        self.assertIn("managed_proxy_setup", completeness["missing_reports"])

    def test_risk_disclosure_contains_current_blockers(self) -> None:
        disclosure = build_risk_disclosure(["managed_proxy_disabled", "cost_attribution:year_specific_cost_drag"])

        self.assertIn("Current blockers", disclosure)
        self.assertIn("managed_proxy_disabled", disclosure["Current blockers"])
        self.assertIn("cost_attribution:year_specific_cost_drag", disclosure["Current blockers"])

    def test_build_payload_does_not_write_active_or_predictions(self) -> None:
        tmp = _workspace_tmp("model-card-build")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_blocked_research_evidence(output)
            payload = build_model_card_payload()

        self.assertFalse(payload["training_invoked"])
        self.assertFalse(payload["active_updated"])
        self.assertFalse(payload["customer_prediction_generated"])
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "customer_predictions").exists())


if __name__ == "__main__":
    unittest.main()
