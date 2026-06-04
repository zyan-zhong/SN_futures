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


class FeatureStoreV12InputContractGateTest(unittest.TestCase):
    def test_missing_or_blocked_input_contract_blocks_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            missing = validate_v12_managed_readiness(managed_rows=[])
            _write_json(
                Path(tmp) / "outputs" / "diagnostics" / "feature_store_v12_input_contract_report.json",
                {"status": "blocked", "input_contract_ready": False, "blocking_reasons": ["production_cache_missing"]},
            )
            blocked = validate_v12_managed_readiness(managed_rows=[])

        self.assertIn("feature_store_v12_input_contract_missing_or_blocked", missing["blocking_reasons"])
        self.assertIn("feature_store_v12_input_contract_missing_or_blocked", blocked["blocking_reasons"])


if __name__ == "__main__":
    unittest.main()
