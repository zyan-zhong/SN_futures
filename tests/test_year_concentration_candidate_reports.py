from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import sys

sys.path.insert(0, "src")

from sn_futures.services.year_concentration_service import refresh_year_concentration


class YearConcentrationCandidateReportsTest(unittest.TestCase):
    def test_refresh_rewrites_v10_report_with_year_evidence_and_blocks_manual_approval_on_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            report_path = output / "model_research" / "candidate_v10" / "candidate_v10_gated_research_report.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(
                    {
                        "status": "success",
                        "candidate_version": "v10",
                        "manual_approval_recommended": True,
                        "gate_passed": True,
                        "v10_gate_checks": {"year_concentration_pass": True},
                        "training_invoked": True,
                        "active_updated": False,
                        "customer_prediction_generated": False,
                    }
                ),
                encoding="utf-8",
            )
            oof_dir = output / "walk_forward" / "v10"
            oof_dir.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(
                {
                    "timestamp": ["2020-01-01", "2020-02-01", "2021-01-01", "2022-01-01"],
                    "predicted_direction": [1, 1, 1, 1],
                    "realized_return": [0.2, 0.2, 0.01, 0.01],
                    "cost_assumption": [0, 0, 0, 0],
                }
            ).to_csv(oof_dir / "oof_trace_5d.csv", index=False)

            summary = refresh_year_concentration()
            updated = json.loads(report_path.read_text(encoding="utf-8"))

        evidence = updated["year_concentration_evidence"]
        self.assertEqual(summary["candidate_v10"]["year_concentration_evidence"]["status"], "fail")
        self.assertEqual(evidence["status"], "fail")
        self.assertIn("year_pnl_concentration_high", evidence["blocking_reasons"])
        self.assertFalse(updated["manual_approval_recommended"])
        self.assertFalse(updated["gate_passed"])
        self.assertFalse(updated["v10_gate_checks"]["year_concentration_pass"])
        self.assertFalse(updated["active_updated"])
        self.assertFalse(updated["customer_prediction_generated"])

    def test_refresh_marks_blocked_v12_year_evidence_skipped_without_oof_or_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            report_path = output / "model_research" / "candidate_v12" / "candidate_v12_gated_research_report.json"
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "candidate_version": "v12",
                        "blocking_reasons": ["training_dataset_v12_blocked", "feature_store_v12_blocked"],
                        "manual_approval_recommended": False,
                        "training_invoked": False,
                        "active_updated": False,
                        "customer_prediction_generated": False,
                    }
                ),
                encoding="utf-8",
            )

            summary = refresh_year_concentration()
            updated = json.loads(report_path.read_text(encoding="utf-8"))

        evidence = updated["year_concentration_evidence"]
        self.assertEqual(evidence["status"], "skipped")
        self.assertFalse(evidence["passed"])
        self.assertIn("candidate_v12_blocked", evidence["blocking_reasons"])
        self.assertIn("oof_trace_missing", evidence["blocking_reasons"])
        self.assertIn("training_not_invoked", evidence["blocking_reasons"])
        self.assertFalse(updated["manual_approval_recommended"])
        self.assertFalse(summary["training_invoked"])
        self.assertFalse(summary["active_updated"])
        self.assertFalse(summary["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
