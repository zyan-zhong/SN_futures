from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.system_report_triage_service import build_system_repair_plan


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_report(root: Path) -> None:
    output_dir = root / "outputs"
    report_json = {
        "generated_at": "2026-05-31T12:47:46",
        "watermark": {
            "current_data_mode": "real",
            "market_history_latest": "2026-05-29",
            "cross_market_updated_at": "",
            "news_updated_at": "",
            "feature_store_updated_at": "",
        },
        "data_consistency": {
            "status": "stale",
            "blocking_reasons": ["market analysis is older than latest market history"],
        },
        "sample_boundary": {
            "sample_mode": False,
            "sample_data_used_for_training": False,
            "sample_data_used_for_backtest": True,
        },
        "api_smoke": {"status": "success", "checked_count": 23, "failed_count": 0},
        "api_performance": {
            "status": "success",
            "endpoints": [
                {"path": "/api/terminal/summary", "elapsed_ms": 75.0, "target_ms": 300, "within_budget": True}
            ],
        },
        "active_absence": {
            "active_status": "none",
            "root_causes": [
                {
                    "category": "data_coverage",
                    "severity": "P0",
                    "evidence": "Missing/low coverage groups: basis, inventory, cross_market",
                    "fix_plan": "Backfill institutional data sources before promotion.",
                },
                {
                    "category": "overfitting",
                    "severity": "P0",
                    "evidence": "PBO=1.0, DSR=0.0, RealityCheck=None",
                    "fix_plan": "Rework validation and feature stability before active promotion.",
                },
            ],
            "blocking_metrics": {
                "pbo": {"value": 1.0, "threshold": 0.2, "passed": False},
                "worst_fold_accuracy": {"value": 0.49, "threshold": 0.52, "passed": False},
                "missing_factor_groups": ["basis", "inventory", "cross_market"],
            },
        },
        "security": {"complete_key_leakage": False, "secret_scan_result": {"status": "not_run"}},
        "recent_tasks": {"tasks": []},
        "active_updated": False,
        "customer_prediction_generated": False,
    }
    (output_dir / "reports").mkdir(parents=True, exist_ok=True)
    (output_dir / "reports" / "full_system_report_latest.txt").write_text(
        "Active status: none\nPBO=1.0\nMissing factor groups: basis inventory cross_market\n",
        encoding="utf-8",
    )
    _write_json(output_dir / "reports" / "full_system_report_latest.json", report_json)
    _write_json(output_dir / "diagnostics" / "all_api_smoke.json", {"status": "success", "failed_count": 0})
    _write_json(
        output_dir / "performance" / "api_performance_report.json",
        {"status": "success", "endpoints": [{"path": "/api/terminal/summary", "within_budget": True}]},
    )
    _write_json(output_dir / "model_registry" / "active_absence_diagnostics.json", report_json["active_absence"])
    _write_json(
        output_dir / "model_registry" / "promotion_report_20260531.json",
        {"status": "failed", "passed": False, "failure_reasons": ["PBO too high"]},
    )
    _write_json(
        output_dir / "research_backtests" / "run_001" / "metrics_1d.json",
        {"probability_of_backtest_overfitting": {"pbo": 0.42}, "worst_fold_accuracy": 0.49},
    )


class SystemReportTriageServiceTest(unittest.TestCase):
    def test_full_system_report_generates_prioritized_repair_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            root = Path(tmp)
            _seed_report(root)

            plan = build_system_repair_plan()

            json_path = root / "outputs" / "diagnostics" / "system_repair_plan.json"
            md_path = root / "outputs" / "diagnostics" / "system_repair_plan.md"
            self.assertEqual(plan["status"], "success")
            self.assertEqual(plan["overall_status"], "blocked_for_prediction")
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            self.assertFalse(plan["active_updated"])
            self.assertFalse(plan["customer_prediction_generated"])

            issues = plan["issues"]
            by_title = "\n".join(str(issue["title"]) for issue in issues)
            by_evidence = "\n".join(str(issue["evidence"]) for issue in issues)
            priorities = {issue["priority"] for issue in issues}
            categories = {issue["category"] for issue in issues}

            self.assertIn("P0", priorities)
            self.assertIn("model", categories)
            self.assertIn("data", categories)
            self.assertIn("active", by_title.lower())
            self.assertIn("basis", by_evidence)
            self.assertIn("inventory", by_evidence)
            self.assertIn("PBO", by_evidence)
            self.assertIn("worst_fold", by_evidence)
            self.assertIn("sample", by_evidence.lower())
            self.assertIn("stale", by_evidence.lower())

            markdown = md_path.read_text(encoding="utf-8")
            self.assertIn("# SNInsightTerminal System Repair Plan", markdown)
            self.assertIn("## P0", markdown)
            self.assertIn("Next Prompt", markdown)


if __name__ == "__main__":
    unittest.main()
