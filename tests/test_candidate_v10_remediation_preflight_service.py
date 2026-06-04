from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.candidate_v10_remediation_preflight_service import (  # noqa: E402
    build_remediation_preflight,
    check_metric_budget,
    estimate_overfitting_risk,
    rank_experiments_for_next_round,
    validate_hypothesis_links,
)


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _base_cost_attribution() -> dict[str, object]:
    return {
        "status": "fail",
        "candidate_version": "v10",
        "failure_drivers": [
            "institutional_2x_cost_negative",
            "institutional_3x_cost_negative",
            "year_specific_cost_drag",
        ],
        "by_year": {
            "rows": [
                {"year": 2022, "net_expectancy_3x": -0.003, "main_failure_driver": "year_specific_cost_drag"},
                {"year": 2023, "net_expectancy_3x": 0.002, "main_failure_driver": "pass"},
            ]
        },
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def _base_remediation() -> dict[str, object]:
    return {
        "status": "ready",
        "candidate_version": "v10",
        "ranked_hypotheses": [
            {
                "id": "cost_aware_thresholding",
                "title": "Cost-aware thresholding",
                "rank_score": 0.6,
                "affected_horizon": "1d",
                "affected_regime": "high_volatility",
                "affected_year": 2022,
                "risk_of_overfitting": "low",
            },
            {
                "id": "stress_2022_filter",
                "title": "2022-like stress filter",
                "rank_score": 0.4,
                "affected_horizon": "1d",
                "affected_regime": "high_volatility",
                "affected_year": 2022,
                "risk_of_overfitting": "high",
            },
        ],
        "recommended_next_experiment": "cost_aware_thresholding",
        "training_invoked": False,
        "active_updated": False,
        "customer_prediction_generated": False,
    }


def _hypothesis(
    hypothesis_id: str,
    *,
    linked_blocker: str = "cost_attribution:institutional_3x_cost_negative",
    primary_metric: str = "institutional_3x_cost_expectancy",
    dataset_version: str = "v10",
    candidate_version: str = "v10",
) -> dict[str, object]:
    return {
        "hypothesis_id": hypothesis_id,
        "status": "open",
        "title": hypothesis_id.replace("_", " "),
        "linked_blocker": linked_blocker,
        "allowed_metrics": [primary_metric, "turnover"],
        "forbidden_metrics": ["final_backtest_pnl"],
        "primary_decision_rule": {"primary_metrics": [primary_metric], "rule": "predeclared OOF-only pass rule"},
        "dataset_version_allowed": dataset_version,
        "candidate_version_allowed": candidate_version,
        "training_allowed": False,
        "active_allowed": False,
        "prediction_allowed": False,
    }


def _write_minimum_reports(output: Path, *, hypotheses: list[dict[str, object]] | None = None) -> None:
    _write_json(output / "model_research" / "candidate_v10" / "v10_cost_failure_research_report.json", _base_remediation())
    _write_json(output / "model_research" / "candidate_v10" / "cost_stress_attribution_v10.json", _base_cost_attribution())
    _write_json(output / "model_research" / "cost_stress_attribution.json", {"candidate_v10": {"cost_stress_attribution": _base_cost_attribution()}})
    _write_json(output / "model_research" / "year_concentration_evidence.json", {"candidate_v10": {"status": "fail", "worst_year": 2022}})
    _write_json(output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json", {"status": "failed", "candidate_version": "v10"})
    _write_json(output / "validation" / "cpcv" / "cpcv_report.json", {"status": "fail", "candidate_version": "v10"})
    _write_json(
        output / "model_research" / "research_decision_board.json",
        {"status": "blocked", "candidate_v12_allowed": False, "manual_approval_recommended": False},
    )
    _write_json(
        output / "model_research" / "hypothesis_registry.json",
        {
            "status": "active" if hypotheses else "empty",
            "hypothesis_count": len(hypotheses or []),
            "hypotheses": hypotheses or [],
            "training_invoked": False,
            "active_updated": False,
            "customer_prediction_generated": False,
        },
    )


class CandidateV10RemediationPreflightServiceTest(unittest.TestCase):
    def test_no_hypothesis_blocks_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_minimum_reports(output, hypotheses=[])

            result = build_remediation_preflight()

        self.assertEqual(result["status"], "blocked")
        self.assertIn("hypothesis_registry_empty", result["blocking_reasons"])
        self.assertFalse(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_no_cost_attribution_blocks_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_minimum_reports(output, hypotheses=[_hypothesis("hyp-cost-aware")])
            (output / "model_research" / "candidate_v10" / "cost_stress_attribution_v10.json").unlink()
            (output / "model_research" / "cost_stress_attribution.json").unlink()

            result = build_remediation_preflight()

        self.assertEqual(result["status"], "blocked")
        self.assertIn("cost_attribution_missing", result["blocking_reasons"])

    def test_repeated_same_metric_sets_high_overfitting_risk(self) -> None:
        hypotheses = [_hypothesis(f"hyp-repeat-{index}") for index in range(4)]

        budget = check_metric_budget(hypotheses)
        risk = estimate_overfitting_risk(hypotheses=hypotheses, remediation_report=_base_remediation(), metric_budget_status=budget)

        self.assertEqual(budget["p_hacking_risk_level"], "high")
        self.assertEqual(risk["risk_level"], "high")
        self.assertIn("repeated_primary_metric:institutional_3x_cost_expectancy", risk["risk_reasons"])

    def test_single_year_improvement_adds_warning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_minimum_reports(output, hypotheses=[_hypothesis("hyp-stress-2022")])

            result = build_remediation_preflight()

        self.assertIn("single_year_improvement_risk:2022", result["warnings"])

    def test_experiment_requiring_v12_data_is_blocked_when_v12_is_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_minimum_reports(output, hypotheses=[_hypothesis("hyp-v12-required", dataset_version="v12", candidate_version="v12")])

            result = build_remediation_preflight()

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["blocked_experiments"][0]["hypothesis_id"], "hyp-v12-required")
        self.assertIn("v12_data_blocked", result["blocked_experiments"][0]["blocking_reasons"])

    def test_preflight_does_not_train_build_or_write_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_minimum_reports(output, hypotheses=[_hypothesis("hyp-cost-aware")])

            with (
                patch("sn_futures.services.candidate_v10_research_service.run_candidate_v10_research") as train,
                patch("sn_futures.services.feature_store_v12_service.build_feature_store_v12") as build_fs,
                patch("sn_futures.services.training_dataset_v12_service.build_training_dataset_v12") as build_td,
            ):
                result = build_remediation_preflight()

            self.assertFalse((output / "model_registry" / "active_model.json").exists())
            self.assertFalse((output / "customer_predictions").exists())

        train.assert_not_called()
        build_fs.assert_not_called()
        build_td.assert_not_called()
        self.assertFalse(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_helpers_validate_links_and_rank_non_blocked_experiments(self) -> None:
        hypotheses = [
            _hypothesis("hyp-cost-aware"),
            _hypothesis("hyp-v12-required", dataset_version="v12", candidate_version="v12"),
        ]
        linked = validate_hypothesis_links(hypotheses, _base_remediation(), _base_cost_attribution())
        ranked = rank_experiments_for_next_round(
            linked_hypotheses=linked["linked_hypotheses"],
            remediation_report=_base_remediation(),
            blocked_experiments=[{"hypothesis_id": "hyp-v12-required"}],
        )

        self.assertEqual(linked["status"], "linked")
        self.assertEqual(ranked[0]["hypothesis_id"], "hyp-cost-aware")
        self.assertNotIn("hyp-v12-required", [row["hypothesis_id"] for row in ranked])


if __name__ == "__main__":
    unittest.main()
