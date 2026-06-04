from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.shadow_replay_evaluator_service import (  # noqa: E402
    build_shadow_replay_evaluator,
    build_shadow_replay_report,
    simulate_shadow_outputs_from_oof,
    validate_shadow_replay_output_isolation,
    validate_shadow_replay_schema,
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


def _write_oof(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "candidate_version,horizon,timestamp,label_start_time,label_end_time,predicted_direction,selected_signal,confidence,regime_label,cost_assumption,trade_edge,expected_return",
                "v10,1d,2022-01-03,2022-01-03,2022-01-04,1,long,0.82,high_volatility,0.0002,0.0100,0.0120",
                "v10,1d,2022-01-04,2022-01-04,2022-01-05,-1,short,0.78,high_volatility,0.0002,0.0090,-0.0110",
                "v10,5d,2022-01-05,2022-01-05,2022-01-10,0,observe,0.12,range,0.0002,0.0000,0.0000",
            ]
        ),
        encoding="utf-8",
    )


def _seed_governance_blocked(output: Path) -> None:
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
        {"status": "blocked", "shadow_mode_allowed": False, "blocked_gates": ["manual_approval_missing"]},
    )
    _write_json(
        output / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json",
        {"status": "blocked", "candidate_version": "v12", "blocking_reasons": ["training_dataset_v12_blocked"]},
    )
    _write_json(
        output / "model_research" / "cost_stress_attribution.json",
        {"status": "fail", "failure_drivers": ["year_specific_cost_drag", "institutional_2x_cost_negative"]},
    )
    _write_json(
        output / "model_research" / "year_concentration_evidence.json",
        {"status": "fail", "blocking_reasons": ["single_year_concentration"]},
    )


class ShadowReplayEvaluatorServiceTest(unittest.TestCase):
    def test_current_blocked_state_without_oof_is_skipped_not_production_ready(self) -> None:
        tmp = _workspace_tmp("shadow-replay-current-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            _seed_governance_blocked(Path(tmp) / "outputs")
            report = build_shadow_replay_report(candidate_version="v10")

        self.assertIn(report["status"], {"blocked", "skipped", "research_only"})
        self.assertNotEqual(report["status"], "production_ready")
        self.assertIn("oof_trace_missing", report["skipped_reasons"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_v12_blocked_is_skipped_even_if_requested(self) -> None:
        tmp = _workspace_tmp("shadow-replay-v12-blocked")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_governance_blocked(output)
            report = build_shadow_replay_report(candidate_version="v12")

        self.assertEqual(report["status"], "skipped")
        self.assertIn("candidate_v12_blocked", report["skipped_reasons"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse((output / "customer_predictions").exists())
        self.assertFalse((output / "model_registry" / "active_model.json").exists())

    def test_v10_oof_generates_research_only_shadow_replay_artifact(self) -> None:
        tmp = _workspace_tmp("shadow-replay-v10-oof")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_governance_blocked(output)
            oof_path = output / "walk_forward" / "v10" / "oof_trace_1d.csv"
            _write_oof(oof_path)
            report = build_shadow_replay_evaluator(candidate_version="v10")
            artifact = json.loads(Path(report["replay_artifact_path"]).read_text(encoding="utf-8"))

        self.assertEqual(report["status"], "research_only")
        self.assertEqual(report["source_candidate_version"], "v10")
        self.assertEqual(report["replay_row_count"], 3)
        self.assertEqual(report["schema_validation_status"], "pass")
        self.assertEqual(report["output_isolation_status"], "pass")
        self.assertTrue(Path(report["replay_artifact_path"]).exists())
        self.assertIn("shadow_mode", report["replay_artifact_path"])
        self.assertEqual(artifact["rows"][0]["mode"], "shadow_replay")
        self.assertTrue(artifact["rows"][0]["not_for_customer_use"])
        self.assertFalse(artifact["rows"][0]["customer_visible"])
        self.assertFalse(artifact["rows"][0]["active_model_used"])
        self.assertIn("high_volatility_exposure", report["risk_tags"])
        self.assertIn("managed_data_blocked", report["risk_tags"])
        self.assertFalse((output / "customer_predictions").exists())
        self.assertFalse((output / "model_registry" / "active_model.json").exists())

    def test_schema_rejects_missing_or_customer_visible_flags(self) -> None:
        row = {
            "mode": "shadow_replay",
            "source_candidate_version": "v10",
            "source_oof_trace_path": "oof.csv",
            "horizon": "1d",
            "instrument": "SN",
            "prediction_timestamp": "2026-06-03T00:00:00",
            "prediction_cutoff_date": "2026-06-03",
            "signal": "observe",
            "confidence": 0.0,
            "technical_regime_label": "range",
            "managed_regime_label": "",
            "risk_tags": [],
            "explanation_summary": "research only",
            "not_for_customer_use": True,
            "customer_visible": False,
            "active_model_used": False,
        }
        missing = dict(row)
        missing.pop("not_for_customer_use")
        visible = {**row, "customer_visible": True}
        active = {**row, "active_model_used": True}

        self.assertEqual(validate_shadow_replay_schema([row])["status"], "pass")
        self.assertEqual(validate_shadow_replay_schema([missing])["status"], "fail")
        self.assertEqual(validate_shadow_replay_schema([visible])["status"], "fail")
        self.assertEqual(validate_shadow_replay_schema([active])["status"], "fail")

    def test_output_isolation_rejects_customer_prediction_paths(self) -> None:
        tmp = _workspace_tmp("shadow-replay-isolation")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            bad = validate_shadow_replay_output_isolation(output / "customer_predictions" / "shadow.json")
            good = validate_shadow_replay_output_isolation(output / "shadow_mode" / "shadow_replay_v10.json")

        self.assertEqual(bad["status"], "fail")
        self.assertIn("shadow_replay_path_collides_with_customer_predictions", bad["blocking_reasons"])
        self.assertEqual(good["status"], "pass")

    def test_simulation_from_oof_marks_rows_research_only(self) -> None:
        tmp = _workspace_tmp("shadow-replay-simulate")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            oof_path = Path(tmp) / "outputs" / "walk_forward" / "v10" / "oof_trace_1d.csv"
            _write_oof(oof_path)
            rows = simulate_shadow_outputs_from_oof(candidate_version="v10", oof_trace_path=oof_path)

        self.assertEqual(len(rows), 3)
        self.assertTrue(all(row["mode"] == "shadow_replay" for row in rows))
        self.assertTrue(all(row["not_for_customer_use"] for row in rows))
        self.assertTrue(all(not row["customer_visible"] for row in rows))
        self.assertTrue(all(not row["active_model_used"] for row in rows))

    def test_report_sanitizes_secret_like_source_reports(self) -> None:
        tmp = _workspace_tmp("shadow-replay-sanitized")
        raw_secret = "shadow-secret-token-1234567890"
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _seed_governance_blocked(output)
            _write_oof(output / "walk_forward" / "v10" / "oof_trace_1d.csv")
            _write_json(
                output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json",
                {"status": "failed", "Authorization": f"Bearer {raw_secret}", "endpoint_secret": raw_secret},
            )
            report = build_shadow_replay_evaluator(candidate_version="v10")

        encoded = json.dumps(report, ensure_ascii=False)
        self.assertNotIn(raw_secret, encoded)
        self.assertFalse(report["training_invoked"])


if __name__ == "__main__":
    unittest.main()
