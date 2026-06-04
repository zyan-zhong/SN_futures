from __future__ import annotations

import os
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.system_stability_audit_service import build_system_stability_audit


class SystemStabilityAuditTest(unittest.TestCase):
    def test_stability_audit_reports_p0_p1_categories_without_active_or_prediction_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            audit = build_system_stability_audit()

        self.assertEqual(audit["status"], "success")
        self.assertIn("process_lifecycle", audit["checks"])
        self.assertIn("data_freshness", audit["checks"])
        self.assertIn("sample_boundary", audit["checks"])
        self.assertFalse(audit["active_updated"])
        self.assertFalse(audit["customer_prediction_generated"])
        self.assertTrue(audit["txt_report_recommended"])


if __name__ == "__main__":
    unittest.main()
