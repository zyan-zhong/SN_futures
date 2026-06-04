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


class NoModelMutationInTriageTest(unittest.TestCase):
    def test_triage_does_not_write_active_or_customer_prediction_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            root = Path(tmp)
            report_dir = root / "outputs" / "reports"
            report_dir.mkdir(parents=True, exist_ok=True)
            (report_dir / "full_system_report_latest.txt").write_text("active_status: none\n", encoding="utf-8")
            _write_json(
                report_dir / "full_system_report_latest.json",
                {
                    "active_absence": {"active_status": "none", "root_causes": []},
                    "watermark": {"current_data_mode": "real"},
                    "active_updated": False,
                    "customer_prediction_generated": False,
                },
            )

            plan = build_system_repair_plan()

            forbidden_paths = [
                root / "outputs" / "model_registry" / "active_model.json",
                root / "outputs" / "models" / "active_model.json",
                root / "outputs" / "sn_live_predictions.json",
                root / "outputs" / "sn_unified_forecast.json",
                root / "outputs" / "customer_predictions.json",
            ]
            self.assertEqual(plan["status"], "success")
            self.assertFalse(plan["active_updated"])
            self.assertFalse(plan["customer_prediction_generated"])
            for path in forbidden_paths:
                self.assertFalse(path.exists(), str(path))


if __name__ == "__main__":
    unittest.main()
