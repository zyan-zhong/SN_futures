from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.warehouse_missing_policy_service import build_warehouse_missing_policy


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class WarehouseMissingPolicyTest(unittest.TestCase):
    def test_fut_wsr_no_sn_rows_generates_missing_policy_without_receipt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            fundamentals = out / "fundamentals"
            _write_json(
                fundamentals / "tushare_provider_status.json",
                {
                    "status": "partial_success",
                    "results": {
                        "tushare_warehouse": {
                            "function_name": "fut_wsr",
                            "attempted": True,
                            "status": "no_sn_rows",
                            "success": False,
                            "row_count": 0,
                            "error_message_zh": "fut_wsr returned no SN rows",
                        }
                    },
                },
            )

            policy = build_warehouse_missing_policy()

            self.assertFalse(policy["warehouse_receipt_available"])
            self.assertEqual(policy["source"], "missing_real_warehouse_receipt")
            self.assertEqual(policy["reason"], "tushare_fut_wsr_no_sn_rows")
            self.assertTrue(policy["no_fake_data"])
            self.assertEqual(policy["inventory_missing_flag"], 1)
            self.assertEqual(policy["model_usage_policy"]["inventory_numeric_factor"], "excluded")
            self.assertEqual(policy["model_usage_policy"]["risk_feature"], "inventory_missing_flag")
            self.assertTrue(Path(policy["policy_path"]).exists())
            self.assertFalse((fundamentals / "sn_tushare_warehouse_receipt.json").exists())
            self.assertFalse((fundamentals / "sn_warehouse_receipts.json").exists())


if __name__ == "__main__":
    unittest.main()
