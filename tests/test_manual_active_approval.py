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

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.active_release_service import approve_active_release


APPROVAL_PHRASE = "我确认仅作为研究预测，不构成投资建议"


ROOT = Path(__file__).resolve().parents[1]


@contextmanager
def _temporary_data_dir() -> Iterator[str]:
    base = ROOT / "app_data" / "test_tmp"
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"manual_active_{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=False)
    try:
        yield str(path)
    finally:
        shutil.rmtree(path, ignore_errors=True)


def _write_pass_reports(root: str) -> Path:
    output = Path(root) / "outputs"
    registry = output / "model_registry"
    validation = output / "institutional_validation"
    registry.mkdir(parents=True, exist_ok=True)
    validation.mkdir(parents=True, exist_ok=True)
    candidate_artifact = registry / "candidate_v5_1d.json"
    candidate_artifact.write_text(json.dumps({"model": "candidate_v5"}, ensure_ascii=False), encoding="utf-8")
    passed_candidate = {
        "model_id": "candidate_v5_1d",
        "horizon": "1d",
        "artifact_path": str(candidate_artifact),
        "metrics": {
            "directional_accuracy": 0.61,
            "cost_adjusted_expectancy": 0.012,
            "brier_score": 0.18,
        },
        "checks": [{"name": "promotion_gate", "passed": True}],
        "feature_columns": ["close", "usd_cny_return"],
        "label_columns": ["direction_1d"],
    }
    promotion_report = {
        "status": "pass",
        "passed": True,
        "dry_run": True,
        "candidate_version": "v5",
        "passed_candidates": [passed_candidate],
        "active_updated": False,
        "sample_data_used": False,
        "baseline_used": False,
    }
    institutional_report = {
        "status": "pass",
        "passed": True,
        "candidate_version": "v5",
        "dry_run": True,
        "deflated_sharpe_ratio": {"passed": True, "deflated_sharpe_ratio": 0.65},
        "probability_of_backtest_overfitting": {"passed": True, "pbo": 0.08},
        "reality_check": {"passed": True, "p_value": 0.03},
        "cost_stress": {"2x": {"passed": True, "expectancy": 0.002}},
        "feature_stability": {"passed": True, "stability_rate": 0.74},
        "sample_data_used": False,
        "baseline_used": False,
        "mock_data_used": False,
    }
    (registry / "promotion_report_v5.json").write_text(json.dumps(promotion_report, ensure_ascii=False), encoding="utf-8")
    (validation / "institutional_validation_report_v5.json").write_text(json.dumps(institutional_report, ensure_ascii=False), encoding="utf-8")
    return output


class ManualActiveApprovalTest(unittest.TestCase):
    def test_manual_approval_publishes_active_after_dry_run_and_human_phrase(self) -> None:
        with _temporary_data_dir() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_pass_reports(tmp)
            result = approve_active_release(
                candidate_version="v5",
                approval_phrase=APPROVAL_PHRASE,
                approver="risk_committee",
                notes="Approved for research prediction display only.",
            )
            self.assertEqual(result["status"], "active_released")
            self.assertTrue(result["active_updated"])
            active_path = output / "model_registry" / "active_model.json"
            self.assertTrue(active_path.exists())
            active = json.loads(active_path.read_text(encoding="utf-8"))
            self.assertEqual(active["candidate_version"], "v5")
            self.assertEqual(active["release_mode"], "manual_human_approval")
            self.assertIn("不构成投资建议", active["disclaimer"])

    def test_approve_active_api_requires_phrase_and_returns_audit_path(self) -> None:
        with _temporary_data_dir() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_pass_reports(tmp)
            status, payload = handle_terminal_api(
                "/api/terminal/models/approve-active",
                method="POST",
                body={
                    "candidate_version": "v5",
                    "approval_phrase": APPROVAL_PHRASE,
                    "approver": "Henry",
                    "notes": "Manual approval API test.",
                },
            )

        self.assertEqual(status, 200)
        self.assertEqual(payload["status"], "active_released")
        self.assertTrue(payload["active_updated"])
        self.assertIn("active_release_audit.json", payload["audit_path"])


if __name__ == "__main__":
    unittest.main()
