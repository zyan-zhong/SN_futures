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


class ActiveReleaseAuditTrailTest(unittest.TestCase):
    def test_active_release_writes_audit_trail_with_checklist_and_no_live_trading(self) -> None:
        with _temporary_data_dir() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = _write_pass_reports(tmp)
            result = approve_active_release(
                candidate_version="v5",
                approval_phrase=APPROVAL_PHRASE,
                approver="approval-owner",
                notes="DSR/PBO/cost stress reviewed.",
            )
            audit_path = Path(result["audit_path"])
            self.assertTrue(audit_path.exists())
            audit = json.loads(audit_path.read_text(encoding="utf-8"))
            self.assertEqual(audit["approver"], "approval-owner")
            self.assertIn("DSR", json.dumps(audit["approval_checklist"], ensure_ascii=False))
            self.assertFalse(audit["live_trading_enabled"])
            self.assertFalse(audit["customer_order_routing_enabled"])
            self.assertEqual(str(audit_path), str(output / "model_registry" / "active_release_audit.json"))


if __name__ == "__main__":
    unittest.main()
