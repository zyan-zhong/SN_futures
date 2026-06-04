from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v12_service import validate_v12_managed_readiness


class ManagedProxyQuarantineSnapshotV12GateTest(unittest.TestCase):
    def test_quarantine_snapshot_ready_never_unlocks_feature_store_v12_without_production_cache(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            diagnostics = Path(tmp) / "outputs" / "diagnostics"
            quarantine = Path(tmp) / "outputs" / "managed_proxy_quarantine"
            diagnostics.mkdir(parents=True, exist_ok=True)
            quarantine.mkdir(parents=True, exist_ok=True)
            snapshot_path = quarantine / "snapshot.json"
            snapshot_path.write_text(json.dumps({"rows": [{"spot_price": 205000}]}), encoding="utf-8")
            (diagnostics / "managed_proxy_quarantine_snapshot_report.json").write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "snapshot_pulled": True,
                        "snapshot_row_count": 1,
                        "quarantine_path": str(snapshot_path),
                        "production_eligible": False,
                        "feature_store_v12_allowed": False,
                        "training_invoked": False,
                        "active_updated": False,
                        "customer_prediction_generated": False,
                    }
                ),
                encoding="utf-8",
            )

            readiness = validate_v12_managed_readiness(managed_rows=[])

        self.assertEqual(readiness["status"], "blocked")
        self.assertFalse(readiness["v12_allowed"])
        self.assertIn("quarantine_snapshot_not_production_data", readiness["blocking_reasons"])
        self.assertFalse(readiness["managed_data_used"])
        self.assertFalse(readiness["training_invoked"])
        self.assertFalse(readiness["active_updated"])
        self.assertFalse(readiness["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
