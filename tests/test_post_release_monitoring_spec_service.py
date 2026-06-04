from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.post_release_monitoring_spec_service import (  # noqa: E402
    build_post_release_monitoring_spec,
    define_cost_drift_sentinels,
    define_pit_regression_sentinels,
    define_prediction_drift_sentinels,
    validate_monitoring_spec_completeness,
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


def _seed_blocked_governance(output: Path) -> None:
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {
            "status": "blocked",
            "current_research_state": "managed_data_blocked",
            "manual_approval_recommended": False,
            "active_publish_allowed": False,
        },
    )
    _write_json(
        output / "model_research" / "shadow_mode_readiness_spec.json",
        {
            "status": "blocked",
            "shadow_mode_allowed": False,
            "blocked_gates": ["manual_approval_missing"],
        },
    )
    _write_json(
        output / "model_research" / "shadow_replay_report.json",
        {
            "status": "research_only",
            "source_candidate_version": "v10",
            "replay_row_count": 500,
            "stability_metrics": {
                "signal_flip_rate": 0.218,
                "horizon_distribution": {"10d": 500},
                "regime_distribution": {"high_volatility": 229, "range": 215, "low_volatility": 56},
            },
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )


class PostReleaseMonitoringSpecServiceTest(unittest.TestCase):
    def test_current_no_active_state_builds_planning_only_spec(self) -> None:
        tmp = _workspace_tmp("post-release-monitoring")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_blocked_governance(output)
            report = build_post_release_monitoring_spec()

        self.assertIn(report["status"], {"planning_only", "blocked"})
        self.assertNotEqual(report["status"], "production_ready")
        self.assertEqual(report["monitoring_mode"], "planning_only")
        self.assertFalse(report["live_monitoring_enabled"])
        self.assertFalse(report["active_model_present"])
        self.assertEqual(report["shadow_replay_status"], "research_only")
        self.assertEqual(report["shadow_replay_source_candidate"], "v10")
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertTrue(Path(report["report_path"]).exists())
        self.assertFalse((output / "model_registry" / "active_model.json").exists())
        self.assertFalse((output / "customer_predictions").exists())

    def test_sentinels_include_customer_prediction_and_active_model_boundaries(self) -> None:
        prediction = define_prediction_drift_sentinels()
        names = {item["id"] for item in prediction}

        self.assertIn("customer_prediction_path_violation", names)
        self.assertIn("active_model_unexpected_existence", names)
        self.assertIn("shadow_output_path_collision", names)

    def test_completeness_fails_when_required_sentinals_are_missing(self) -> None:
        spec = {
            "data_drift_sentinels": [],
            "prediction_drift_sentinels": [],
            "cost_drift_sentinels": [],
            "pit_regression_sentinels": [],
        }
        result = validate_monitoring_spec_completeness(spec)

        self.assertEqual(result["status"], "fail")
        self.assertIn("pit_timestamp_regression_sentinel_missing", result["blocking_reasons"])
        self.assertIn("cost_drift_sentinel_missing", result["blocking_reasons"])
        self.assertIn("customer_prediction_path_sentinel_missing", result["blocking_reasons"])
        self.assertIn("active_model_unexpected_existence_sentinel_missing", result["blocking_reasons"])

    def test_cost_and_pit_sentinels_are_defined_by_public_helpers(self) -> None:
        cost_names = {item["id"] for item in define_cost_drift_sentinels()}
        pit_names = {item["id"] for item in define_pit_regression_sentinels()}

        self.assertIn("cost_drag_drift", cost_names)
        self.assertIn("two_x_cost_expectancy_negative", cost_names)
        self.assertIn("pit_timestamp_regression", pit_names)
        self.assertIn("stale_evidence_regression", pit_names)

    def test_missing_data_quality_and_shadow_replay_reports_are_warnings(self) -> None:
        tmp = _workspace_tmp("post-release-monitoring-missing")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            report = build_post_release_monitoring_spec()

        self.assertIn("data_quality_report_missing", report["warning_reasons"])
        self.assertIn("shadow_replay_report_missing", report["warning_reasons"])
        self.assertIn("shadow_replay_report_missing", report["readiness_gaps"])
        self.assertFalse(report["live_monitoring_enabled"])


if __name__ == "__main__":
    unittest.main()
