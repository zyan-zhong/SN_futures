from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.rollback_rehearsal_service import (  # noqa: E402
    build_rollback_rehearsal_plan,
    detect_unapproved_artifacts,
    simulate_artifact_quarantine,
    validate_quarantine_manifest,
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


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class RollbackRehearsalServiceTest(unittest.TestCase):
    def test_current_no_artifacts_builds_ready_report_without_side_effects(self) -> None:
        tmp = _workspace_tmp("rollback-clean")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            report = build_rollback_rehearsal_plan()

        self.assertIn(report["status"], {"pass", "ready"})
        self.assertFalse(report["quarantine_needed"])
        self.assertEqual(report["artifacts_detected"], [])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertTrue(Path(report["report_path"]).exists())
        self.assertFalse((tmp / "outputs" / "model_registry" / "active_model.json").exists())
        self.assertFalse((tmp / "outputs" / "customer_predictions").exists())

    def test_active_model_and_customer_prediction_artifacts_are_detected(self) -> None:
        tmp = _workspace_tmp("rollback-artifacts")
        out = tmp / "outputs"
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            _write_json(out / "model_registry" / "active_model.json", {"status": "unexpected"})
            _write_text(out / "customer_predictions.json", '{"prediction": "unexpected"}')

            artifacts = detect_unapproved_artifacts()
            report = build_rollback_rehearsal_plan()

        artifact_types = {item["artifact_type"] for item in artifacts}
        self.assertIn("active_model_json", artifact_types)
        self.assertIn("customer_predictions_json", artifact_types)
        self.assertTrue(report["quarantine_needed"])
        self.assertIn("quarantine_unapproved_artifacts", report["manual_actions_required"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_shadow_artifact_under_customer_predictions_and_active_pointer_are_detected(self) -> None:
        tmp = _workspace_tmp("rollback-shadow-pointer")
        out = tmp / "outputs"
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            _write_json(out / "customer_predictions" / "shadow_mode" / "shadow_v10.json", {"mode": "shadow"})
            _write_json(out / "model_registry" / "active_pointer.json", {"active": "candidate_v10"})

            artifacts = detect_unapproved_artifacts()

        artifact_types = {item["artifact_type"] for item in artifacts}
        self.assertIn("shadow_output_customer_prediction_collision", artifact_types)
        self.assertIn("registry_active_pointer", artifact_types)

    def test_quarantine_simulation_does_not_delete_or_move_real_files(self) -> None:
        tmp = _workspace_tmp("rollback-sim")
        out = tmp / "outputs"
        active = out / "model_registry" / "active_model.json"
        prediction = out / "customer_predictions.json"
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            _write_json(active, {"status": "unexpected"})
            _write_text(prediction, '{"prediction": "unexpected"}')

            manifest = simulate_artifact_quarantine()

        self.assertTrue(active.exists())
        self.assertTrue(prediction.exists())
        self.assertTrue(manifest["simulation_only"])
        self.assertGreaterEqual(len(manifest["actions"]), 2)
        for action in manifest["actions"]:
            self.assertTrue(action["simulation_only"])
            self.assertIn("original_path", action)
            self.assertIn("artifact_type", action)
            self.assertIn("reason", action)
            self.assertIn("recommended_action", action)

    def test_quarantine_manifest_schema_and_secret_sanitization(self) -> None:
        manifest = simulate_artifact_quarantine(
            artifacts=[
                {
                    "original_path": "Authorization: Bearer raw-secret-token-should-not-appear",
                    "artifact_type": "active_model_json",
                    "reason": "SN_TUSHARE_TOKEN=raw-secret-token-should-not-appear",
                    "recommended_action": "simulation only",
                }
            ],
            write=False,
            record_run=False,
        )
        validation = validate_quarantine_manifest(manifest)
        serialized = json.dumps(manifest, ensure_ascii=False)

        self.assertEqual(validation["status"], "pass")
        self.assertNotIn("raw-secret-token-should-not-appear", serialized)
        self.assertNotIn("Authorization: Bearer", serialized)


if __name__ == "__main__":
    unittest.main()
