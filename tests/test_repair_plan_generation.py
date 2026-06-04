from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _seed_minimal_report(root: Path) -> None:
    output_dir = root / "outputs"
    report_dir = output_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    (report_dir / "full_system_report_latest.txt").write_text("No active model. PBO=1.0.\n", encoding="utf-8")
    _write_json(
        report_dir / "full_system_report_latest.json",
        {
            "active_absence": {
                "active_status": "none",
                "root_causes": [
                    {"category": "validation", "severity": "P0", "evidence": "Latest promotion failed."}
                ],
                "blocking_metrics": {
                    "pbo": {"value": 1.0, "threshold": 0.2, "passed": False},
                    "worst_fold_accuracy": {"value": 0.51, "threshold": 0.52, "passed": False},
                },
            },
            "watermark": {"current_data_mode": "real"},
            "data_consistency": {"status": "consistent", "blocking_reasons": []},
            "api_smoke": {"failed_count": 0},
        },
    )


class RepairPlanGenerationApiTest(unittest.TestCase):
    def test_terminal_api_builds_and_reads_repair_plan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            root = Path(tmp)
            _seed_minimal_report(root)

            status, payload = handle_terminal_api(
                "/api/terminal/diagnostics/build-repair-plan",
                method="POST",
                body={},
            )

            self.assertEqual(status, 200)
            self.assertEqual(payload["status"], "success")
            self.assertEqual(payload["overall_status"], "blocked_for_prediction")
            self.assertTrue(payload["issues"])
            self.assertTrue(str(payload["markdown_path"]).endswith("system_repair_plan.md"))
            self.assertTrue(str(payload["json_path"]).endswith("system_repair_plan.json"))

            status, latest = handle_terminal_api("/api/terminal/diagnostics/repair-plan", method="GET")
            self.assertEqual(status, 200)
            self.assertEqual(latest["status"], "success")
            self.assertEqual(latest["overall_status"], payload["overall_status"])
            self.assertEqual(latest["issues"][0]["priority"], payload["issues"][0]["priority"])


if __name__ == "__main__":
    unittest.main()
