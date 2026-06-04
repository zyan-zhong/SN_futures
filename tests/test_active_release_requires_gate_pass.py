from __future__ import annotations

import json
import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from test_manual_active_approval import APPROVAL_PHRASE, _temporary_data_dir, _write_pass_reports
from sn_futures.services.active_release_service import approve_active_release


class ActiveReleaseRequiresGatePassTest(unittest.TestCase):
    def test_rejects_when_promotion_dry_run_did_not_pass(self) -> None:
        with _temporary_data_dir() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_pass_reports(tmp)
            report_path = output / "model_registry" / "promotion_report_v5.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))
            report["passed"] = False
            report["status"] = "failed"
            report["passed_candidates"] = []
            report_path.write_text(json.dumps(report, ensure_ascii=False), encoding="utf-8")

            result = approve_active_release(candidate_version="v5", approval_phrase=APPROVAL_PHRASE, approver="risk")

            self.assertEqual(result["status"], "rejected")
            self.assertFalse(result["active_updated"])
            self.assertIn("promotion dry-run", json.dumps(result["blocking_reasons"], ensure_ascii=False))
            self.assertFalse((output / "model_registry" / "active_model.json").exists())

    def test_rejects_when_institutional_validation_or_human_phrase_fails(self) -> None:
        with _temporary_data_dir() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_pass_reports(tmp)
            validation_path = output / "institutional_validation" / "institutional_validation_report_v5.json"
            validation = json.loads(validation_path.read_text(encoding="utf-8"))
            validation["deflated_sharpe_ratio"]["passed"] = False
            validation_path.write_text(json.dumps(validation, ensure_ascii=False), encoding="utf-8")

            result = approve_active_release(candidate_version="v5", approval_phrase="approve", approver="risk")

            self.assertEqual(result["status"], "rejected")
            self.assertFalse(result["active_updated"])
            dumped = json.dumps(result["blocking_reasons"], ensure_ascii=False)
            self.assertIn("human approval phrase", dumped)
            self.assertIn("DSR", dumped)
            self.assertFalse((output / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()
