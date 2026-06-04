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


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class ManagedDataProductionCacheGateV12Test(unittest.TestCase):
    def test_missing_production_cache_gate_blocks_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            readiness = validate_v12_managed_readiness(managed_rows=[])

        self.assertFalse(readiness["v12_allowed"])
        self.assertIn("production_cache_gate_missing_or_blocked", readiness["blocking_reasons"])

    def test_dry_run_ready_without_written_cache_still_blocks_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_json(
                Path(tmp) / "outputs" / "diagnostics" / "managed_data_production_cache_gate_report.json",
                {
                    "status": "ready",
                    "production_cache_write_allowed": False,
                    "production_cache_written": False,
                    "feature_store_v12_allowed": False,
                    "dry_run_plan": {"status": "ready"},
                    "blocking_reasons": [],
                },
            )
            readiness = validate_v12_managed_readiness(managed_rows=[])

        self.assertFalse(readiness["v12_allowed"])
        self.assertIn("production_cache_not_written", readiness["blocking_reasons"])
        self.assertIn("production_cache_write_not_allowed", readiness["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
