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
from sn_futures.services.managed_data_audit_service import build_managed_audit_manifest, compute_managed_audit_readiness
from sn_futures.services.managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS
from sn_futures.services.managed_pit_replay_service import build_pit_replay_report


def complete_row() -> dict:
    row = {
        "feature_date": "2026-01-10",
        "prediction_cutoff_date": "2026-01-10",
        "source_timestamp": "2026-01-09T09:00:00",
        "asof_date": "2026-01-09",
        "ingest_timestamp": "2026-01-12T10:00:00",
    }
    for field in MANAGED_REQUIRED_RESEARCH_FIELDS:
        row[field] = 1
    return row


class ManagedPitReplayAuditV12GateTest(unittest.TestCase):
    def test_replay_fail_blocks_audit_readiness_without_running_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.managed_data_audit_service.load_latest_managed_health",
            return_value={"status": "ready", "provider_status": "success_with_required_fields", "v12_allowed": True, "blocking_reasons": []},
        ), patch("sn_futures.services.feature_store_v12_service.build_feature_store_v12") as build_v12:
            build_pit_replay_report(rows=[], cutoffs=["2026-01-10"], write=True)
            manifest = build_managed_audit_manifest(rows=[complete_row()])
            readiness = compute_managed_audit_readiness()

        build_v12.assert_not_called()
        self.assertEqual(manifest["status"], "blocked")
        self.assertEqual(readiness["status"], "blocked")
        self.assertFalse(readiness["v12_allowed"])
        self.assertIn("pit_replay_failed", readiness["blocking_reasons"])
        self.assertFalse(readiness["training_invoked"])
        self.assertFalse(readiness["active_updated"])
        self.assertFalse(readiness["customer_prediction_generated"])

    def test_v12_gate_blocks_when_existing_replay_report_failed_without_running_replay(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.feature_store_v12_service.run_pit_replay_harness"
        ) as run_replay:
            build_pit_replay_report(rows=[], cutoffs=["2026-01-10"], write=True)
            readiness = validate_v12_managed_readiness(
                health={"status": "ready", "provider_status": "success_with_required_fields", "v12_allowed": True, "blocking_reasons": []},
                audit={
                    "status": "ready",
                    "v12_allowed": True,
                    "blocking_reasons": [],
                    "leakage_checks": {
                        "source_timestamp_leakage_pass": True,
                        "asof_date_leakage_pass": True,
                        "feature_date_cutoff_pass": True,
                        "ingest_timestamp_not_used_as_asof_pass": True,
                        "point_in_time_join_ready": True,
                    },
                },
                schema_mapping={"status": "ready", "schema_mapping_ready": True, "blocking_reasons": []},
                managed_rows=[complete_row()],
            )

        run_replay.assert_not_called()
        self.assertEqual(readiness["status"], "blocked")
        self.assertFalse(readiness["v12_allowed"])
        self.assertIn("pit_replay_failed", readiness["blocking_reasons"])
        self.assertFalse(readiness["training_invoked"])
        self.assertFalse(readiness["active_updated"])
        self.assertFalse(readiness["customer_prediction_generated"])

    def test_audit_manifest_includes_replay_summary_when_present(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.managed_data_audit_service.load_latest_managed_health",
            return_value={"status": "ready", "provider_status": "success_with_required_fields", "v12_allowed": True, "blocking_reasons": []},
        ):
            replay = build_pit_replay_report(rows=[complete_row()], cutoffs=["2026-01-10"], write=True)
            manifest = build_managed_audit_manifest(rows=[complete_row()])

        serialized = json.dumps(manifest, ensure_ascii=False)
        self.assertEqual(replay["status"], "ready")
        self.assertEqual(manifest["pit_replay_summary"]["status"], "ready")
        self.assertTrue(manifest["pit_replay_summary"]["point_in_time_join_ready"])
        self.assertNotIn("Authorization", serialized)


if __name__ == "__main__":
    unittest.main()
