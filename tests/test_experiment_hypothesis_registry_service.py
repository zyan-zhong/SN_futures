from __future__ import annotations

import json
import os
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.experiment_hypothesis_registry_service import (
    attach_hypothesis_to_future_experiment,
    build_anti_p_hacking_ledger,
    create_hypothesis_entry,
    list_hypothesis_registry,
    validate_hypothesis_entry,
)


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "tmp_test_runs"


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _workspace_tmp(name: str) -> Path:
    TMP_ROOT.mkdir(parents=True, exist_ok=True)
    path = TMP_ROOT / f"{name}-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


class ExperimentHypothesisRegistryServiceTest(unittest.TestCase):
    def test_missing_primary_decision_rule_is_invalid(self) -> None:
        result = validate_hypothesis_entry(
            {
                "title": "Reduce 1d cost drag",
                "linked_blocker": "cost_attribution:institutional_3x_cost_negative",
                "allowed_metrics": ["cost_adjusted_expectancy"],
                "forbidden_metrics": ["final_backtest_pnl"],
            }
        )

        self.assertEqual(result["status"], "invalid")
        self.assertIn("primary_decision_rule_missing", result["blocking_reasons"])

    def test_missing_linked_blocker_is_invalid(self) -> None:
        result = validate_hypothesis_entry(
            {
                "title": "Reduce 1d cost drag",
                "primary_decision_rule": "pass if 3x cost expectancy >= 0 on OOF-only estimate",
                "allowed_metrics": ["cost_adjusted_expectancy"],
                "forbidden_metrics": ["final_backtest_pnl"],
            }
        )

        self.assertEqual(result["status"], "invalid")
        self.assertIn("linked_blocker_missing", result["blocking_reasons"])

    def test_too_many_primary_metrics_is_invalid(self) -> None:
        result = validate_hypothesis_entry(
            {
                "title": "Too broad",
                "linked_blocker": "validation:pbo_or_cpcv_missing_or_failed",
                "primary_decision_rule": {
                    "primary_metrics": ["pbo", "reality_check", "cost_expectancy"],
                    "rule": "all pass",
                },
                "allowed_metrics": ["pbo", "reality_check", "cost_expectancy"],
                "forbidden_metrics": ["final_backtest_pnl"],
            }
        )

        self.assertEqual(result["status"], "invalid")
        self.assertIn("too_many_primary_metrics", result["blocking_reasons"])

    def test_forbidden_metric_used_as_primary_is_invalid(self) -> None:
        result = validate_hypothesis_entry(
            {
                "title": "P-hacking risk",
                "linked_blocker": "validation:reality_check_missing_or_failed",
                "primary_decision_rule": {
                    "primary_metrics": ["final_backtest_pnl"],
                    "rule": "maximize pnl",
                },
                "allowed_metrics": ["reality_check"],
                "forbidden_metrics": ["final_backtest_pnl"],
            }
        )

        self.assertEqual(result["status"], "invalid")
        self.assertIn("forbidden_metric_used_as_primary", result["blocking_reasons"])

    def test_create_hypothesis_entry_defaults_no_training_active_prediction_and_sanitizes(self) -> None:
        tmp = _workspace_tmp("hypothesis-create")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            entry = create_hypothesis_entry(
                {
                    "title": "Cost-aware thresholding",
                    "motivation": "raw-secret-token-should-not-appear",
                    "linked_blocker": "cost_attribution:institutional_3x_cost_negative",
                    "expected_direction": "reduce 3x cost drag without increasing PBO",
                    "allowed_metrics": ["institutional_3x_cost_expectancy"],
                    "forbidden_metrics": ["final_backtest_pnl"],
                    "primary_decision_rule": {
                        "primary_metrics": ["institutional_3x_cost_expectancy"],
                        "rule": "3x cost expectancy must be non-negative on predeclared OOF-only estimate",
                    },
                    "secondary_diagnostics": ["trade_count", "turnover"],
                    "dataset_version_allowed": "v10",
                    "candidate_version_allowed": "v10",
                }
            )
            registry = list_hypothesis_registry()
            serialized = json.dumps(registry, ensure_ascii=False)

        self.assertEqual(entry["status"], "open")
        self.assertFalse(entry["training_allowed"])
        self.assertFalse(entry["active_allowed"])
        self.assertFalse(entry["prediction_allowed"])
        self.assertEqual(registry["hypothesis_count"], 1)
        self.assertNotIn("raw-secret-token-should-not-appear", serialized)

    def test_experiment_without_hypothesis_id_is_blocked(self) -> None:
        result = attach_hypothesis_to_future_experiment({"candidate_version": "v12"})

        self.assertEqual(result["status"], "blocked")
        self.assertIn("hypothesis_id_missing", result["blocking_reasons"])
        self.assertFalse(result["training_allowed"])

    def test_ledger_reports_budget_and_does_not_change_manual_approval_or_train(self) -> None:
        tmp = _workspace_tmp("hypothesis-ledger")
        with patch.dict(os.environ, {"SN_DATA_DIR": str(tmp)}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "model_research" / "research_decision_board.json",
                {
                    "status": "blocked",
                    "manual_approval_recommended": False,
                    "blocking_reasons": ["cost_attribution:institutional_3x_cost_negative"],
                },
            )
            create_hypothesis_entry(
                {
                    "title": "Cost-aware thresholding",
                    "linked_blocker": "cost_attribution:institutional_3x_cost_negative",
                    "expected_direction": "improve cost stress",
                    "allowed_metrics": ["institutional_3x_cost_expectancy"],
                    "forbidden_metrics": ["final_backtest_pnl"],
                    "primary_decision_rule": {"primary_metrics": ["institutional_3x_cost_expectancy"], "rule": ">= 0"},
                }
            )

            ledger = build_anti_p_hacking_ledger()
            board = json.loads((output / "model_research" / "research_decision_board.json").read_text(encoding="utf-8"))

        self.assertEqual(ledger["status"], "active")
        self.assertEqual(ledger["hypothesis_count"], 1)
        self.assertEqual(ledger["experiment_budget_by_blocker"]["cost_attribution:institutional_3x_cost_negative"]["registered_hypotheses"], 1)
        self.assertEqual(ledger["p_hacking_risk_level"], "low")
        self.assertFalse(ledger["training_invoked"])
        self.assertFalse(ledger["active_updated"])
        self.assertFalse(ledger["customer_prediction_generated"])
        self.assertFalse(board["manual_approval_recommended"])


if __name__ == "__main__":
    unittest.main()
