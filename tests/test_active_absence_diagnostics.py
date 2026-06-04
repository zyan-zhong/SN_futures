from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.active_absence_diagnostics_service import build_active_absence_diagnostics
from active_absence_fixture import write_blocked_candidate_fixture


class ActiveAbsenceDiagnosticsTest(unittest.TestCase):
    def test_no_active_outputs_root_causes_and_does_not_write_active_or_predictions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = write_blocked_candidate_fixture(tmp)
            report = build_active_absence_diagnostics()

            self.assertEqual(report["active_status"], "none")
            self.assertFalse(report["active_updated"])
            self.assertFalse(report["customer_prediction_generated"])
            self.assertFalse((output / "model_registry" / "active_model.json").exists())
            categories = {item["category"] for item in report["root_causes"]}
            self.assertTrue({"data_coverage", "model_stability", "overfitting", "cost"}.issubset(categories))
            self.assertIn("candidate_v6_plan", report)

    def test_api_endpoint_returns_json_safe_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            write_blocked_candidate_fixture(tmp)
            status, payload = handle_terminal_api("/api/terminal/models/active-absence-diagnostics")
            json.dumps(payload, ensure_ascii=False, allow_nan=False)

        self.assertEqual(status, 200)
        self.assertEqual(payload["active_status"], "none")
        self.assertIn("blocking_metrics", payload)


if __name__ == "__main__":
    unittest.main()
