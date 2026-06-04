from __future__ import annotations

import json
import os
import shutil
import sys
import unittest
import uuid
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.active_release_service import REQUIRED_APPROVAL_PHRASE, approve_active_release


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _temporary_data_dir() -> Iterator[str]:
    base = ROOT / "app_data" / "test_tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"active_gate_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _write_v9_reports(root: str, *, validation_overrides: dict | None = None, promotion_overrides: dict | None = None) -> Path:
    output = Path(root) / "outputs"
    registry = output / "model_registry"
    validation_dir = output / "institutional_validation"
    registry.mkdir(parents=True, exist_ok=True)
    validation_dir.mkdir(parents=True, exist_ok=True)
    artifact = registry / "candidate_v9_10d.json"
    _write(artifact, {"model": "candidate_v9"})
    promotion = {
        "status": "pass",
        "passed": True,
        "dry_run": True,
        "candidate_version": "v9",
        "passed_candidates": [
            {
                "model_id": "candidate_v9_10d",
                "horizon": "10d",
                "artifact_path": str(artifact),
                "metrics": {"cost_adjusted_expectancy": 0.02},
                "checks": [{"name": "promotion_dry_run", "passed": True}],
                "feature_columns": ["settlement_basis_to_close"],
                "label_columns": ["direction_10d"],
            }
        ],
        "active_updated": False,
        "customer_prediction_generated": False,
        "sample_data_used": False,
        "mock_data_used": False,
        "baseline_used": False,
    }
    institutional = {
        "status": "pass",
        "passed": True,
        "candidate_version": "v9",
        "dry_run": True,
        "deflated_sharpe_ratio": {"deflated_sharpe_ratio": 1.25},
        "probability_of_backtest_overfitting": {"pbo": 0.08},
        "reality_check": {"passed": True, "p_value": 0.03},
        "cost_stress": {
            "2x_cost": {"expectancy": 0.004, "active_eligibility_under_cost_stress": True},
            "3x_cost": {"expectancy": 0.003, "active_eligibility_under_cost_stress": True},
        },
        "dominance_checks": {
            "single_fold_contribution": 0.26,
            "single_fold_dominates": False,
            "single_year_contribution": 0.35,
            "single_year_dominates": False,
            "single_regime_contribution": 0.55,
            "single_regime_dominates": False,
        },
        "feature_stability": {"passed": True, "stability_score": 0.72},
        "promotion_eligibility": {
            "eligible": True,
            "checks": [
                {"name": "PBO", "passed": True},
                {"name": "Reality Check", "passed": True},
                {"name": "no single fold dominates", "passed": True},
                {"name": "no single year dominates", "passed": True},
                {"name": "no single regime dominates", "passed": True},
                {"name": "feature stability", "passed": True},
            ],
            "failure_reasons": [],
        },
        "active_updated": False,
        "customer_prediction_generated": False,
        "sample_data_used": False,
        "mock_data_used": False,
        "baseline_used": False,
    }
    promotion.update(promotion_overrides or {})
    institutional.update(validation_overrides or {})
    _write(registry / "promotion_report_v9.json", promotion)
    _write(validation_dir / "institutional_validation_report_v9.json", institutional)
    return output


class CandidateV9ActiveApprovalGateTest(unittest.TestCase):
    def test_rejects_current_v9_like_report_even_when_promotion_dry_run_passed(self) -> None:
        with _temporary_data_dir() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_v9_reports(
                tmp,
                validation_overrides={
                    "status": "failed",
                    "passed": False,
                    "probability_of_backtest_overfitting": {"pbo": 0.6},
                    "reality_check": {"passed": False, "p_value": 0.095},
                    "dominance_checks": {"single_regime_contribution": 0.798, "single_regime_dominates": True},
                    "promotion_eligibility": {
                        "eligible": False,
                        "failure_reasons": ["PBO 过高，存在过拟合风险", "Reality Check 未通过", "单一 regime 贡献过高"],
                    },
                },
            )

            result = approve_active_release(candidate_version="v9", approval_phrase=REQUIRED_APPROVAL_PHRASE, approver="risk")

            self.assertEqual(result["status"], "rejected")
            self.assertFalse(result["active_updated"])
            dumped = json.dumps(result["blocking_reasons"], ensure_ascii=False)
            self.assertIn("institutional validation", dumped)
            self.assertIn("PBO", dumped)
            self.assertIn("Reality Check", dumped)
            self.assertIn("regime", dumped)
            self.assertFalse((output / "model_registry" / "active_model.json").exists())

    def test_v9_requires_3x_cost_worst_slices_and_no_sample_mock_baseline(self) -> None:
        with _temporary_data_dir() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_v9_reports(
                tmp,
                validation_overrides={
                    "cost_stress": {
                        "2x_cost": {"expectancy": 0.004, "active_eligibility_under_cost_stress": True},
                        "3x_cost": {"expectancy": -0.001, "active_eligibility_under_cost_stress": False},
                    },
                    "dominance_checks": {"single_fold_dominates": False, "single_year_dominates": True, "single_regime_dominates": False},
                    "sample_data_used": True,
                },
            )

            result = approve_active_release(candidate_version="v9", approval_phrase=REQUIRED_APPROVAL_PHRASE, approver="risk")

            self.assertEqual(result["status"], "rejected")
            dumped = json.dumps(result["blocking_reasons"], ensure_ascii=False)
            self.assertIn("3x", dumped)
            self.assertIn("year", dumped)
            self.assertIn("mock/sample/baseline", dumped)
            self.assertFalse((output / "model_registry" / "active_model.json").exists())

    def test_v9_all_gates_and_human_phrase_allow_manual_active_release_only_when_called(self) -> None:
        with _temporary_data_dir() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_v9_reports(tmp)
            self.assertFalse((output / "model_registry" / "active_model.json").exists())

            result = approve_active_release(candidate_version="v9", approval_phrase=REQUIRED_APPROVAL_PHRASE, approver="risk_committee")

            self.assertEqual(result["status"], "active_released")
            self.assertTrue(result["active_updated"])
            self.assertEqual(result["candidate_version"], "v9")
            active_path = output / "model_registry" / "active_model.json"
            audit_path = output / "model_registry" / "active_release_audit.json"
            self.assertTrue(active_path.exists())
            self.assertTrue(audit_path.exists())
            active = json.loads(active_path.read_text(encoding="utf-8"))
            self.assertEqual(active["candidate_version"], "v9")
            self.assertFalse(active["live_trading_enabled"])
            self.assertFalse(active["customer_order_routing_enabled"])


if __name__ == "__main__":
    unittest.main()
