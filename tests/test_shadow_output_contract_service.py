from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.shadow_output_contract_service import (  # noqa: E402
    build_shadow_output_contract,
    build_shadow_output_contract_report,
    build_shadow_output_dry_run_artifact,
    detect_customer_prediction_path_collision,
    validate_shadow_output_path_isolation,
    validate_shadow_output_schema,
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


class ShadowOutputContractServiceTest(unittest.TestCase):
    def test_current_blocked_state_disallows_real_shadow_output(self) -> None:
        tmp = _workspace_tmp("shadow-output-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            report = build_shadow_output_contract_report()

        self.assertEqual(report["status"], "blocked")
        self.assertFalse(report["shadow_output_allowed"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertIn("manual_approval_missing", report["blocking_reasons"])

    def test_dry_run_artifact_is_contract_only_and_isolated(self) -> None:
        tmp = _workspace_tmp("shadow-output-dry-run")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            artifact = build_shadow_output_dry_run_artifact(synthetic_contract_only=True)

        self.assertTrue(artifact["dry_run_artifact_created"])
        self.assertTrue(artifact["synthetic_contract_only"])
        self.assertEqual(artifact["mode"], "shadow")
        self.assertTrue(artifact["not_for_customer_use"])
        self.assertFalse(artifact["active_model_used"])
        self.assertFalse(artifact["customer_visible"])
        self.assertFalse(artifact["customer_prediction_generated"])
        self.assertFalse((tmp / "outputs" / "customer_predictions").exists())
        self.assertFalse((tmp / "outputs" / "model_registry" / "active_model.json").exists())
        self.assertIn("shadow_mode", artifact["artifact_path"])

    def test_schema_rejects_customer_visible_active_or_missing_safety_flags(self) -> None:
        valid = {
            "generated_at": "2026-06-03T00:00:00",
            "mode": "shadow",
            "candidate_version": "v12",
            "model_version_or_candidate_id": "candidate_v12",
            "horizon": "1d",
            "instrument": "SN",
            "prediction_timestamp": "2026-06-03T00:00:00",
            "prediction_cutoff_date": "2026-06-03",
            "signal": "contract_placeholder",
            "confidence": 0.0,
            "explanation_summary": "schema placeholder only",
            "not_for_customer_use": True,
            "active_model_used": False,
            "customer_visible": False,
        }
        missing_flag = dict(valid)
        missing_flag.pop("not_for_customer_use")
        visible = {**valid, "customer_visible": True}
        active = {**valid, "active_model_used": True}

        self.assertEqual(validate_shadow_output_schema(valid)["status"], "pass")
        self.assertEqual(validate_shadow_output_schema(missing_flag)["status"], "fail")
        self.assertEqual(validate_shadow_output_schema(visible)["status"], "fail")
        self.assertEqual(validate_shadow_output_schema(active)["status"], "fail")

    def test_path_isolation_and_customer_prediction_collision_are_enforced(self) -> None:
        tmp = _workspace_tmp("shadow-output-collision")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = tmp / "outputs"
            collision = validate_shadow_output_path_isolation(output / "customer_predictions" / "shadow.json")
            safe = validate_shadow_output_path_isolation(output / "shadow_mode" / "shadow.json")
            _write_json(output / "customer_predictions" / "shadow.json", {"status": "forbidden"})
            detected = detect_customer_prediction_path_collision()

        self.assertEqual(collision["status"], "fail")
        self.assertIn("shadow_output_path_collides_with_customer_predictions", collision["blocking_reasons"])
        self.assertEqual(safe["status"], "pass")
        self.assertEqual(detected["status"], "fail")
        self.assertIn("customer_prediction_path_exists", detected["blocking_reasons"])

    def test_contract_report_records_dry_run_without_real_prediction_or_active(self) -> None:
        tmp = _workspace_tmp("shadow-output-report")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            contract = build_shadow_output_contract()
            artifact = build_shadow_output_dry_run_artifact(synthetic_contract_only=True)
            report = build_shadow_output_contract_report()

        self.assertIn("shadow_mode", contract["shadow_output_root"])
        self.assertTrue(artifact["dry_run_artifact_created"])
        self.assertTrue(report["dry_run_artifact_created"])
        self.assertEqual(report["schema_validation_status"], "pass")
        self.assertEqual(report["path_isolation_status"], "pass")
        self.assertEqual(report["customer_prediction_collision_status"], "pass")
        self.assertFalse(report["shadow_output_allowed"])
        self.assertFalse((tmp / "outputs" / "customer_predictions").exists())
        self.assertFalse((tmp / "outputs" / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()
