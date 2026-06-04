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


class NoFakeWarehouseReceiptTest(unittest.TestCase):
    def test_no_sn_rows_and_non_sn_fallback_do_not_create_fake_warehouse_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            fundamentals = out / "fundamentals"
            _write_json(
                fundamentals / "tushare_provider_status.json",
                {"results": {"tushare_warehouse": {"status": "no_sn_rows", "attempted": True, "row_count": 0}}},
            )
            _write_json(
                fundamentals / "managed_fundamentals.json",
                {"rows": [{"trade_date": "2026-01-02", "product": "CU", "shfe_warehouse_receipt": 5000}]},
            )

            policy = build_warehouse_missing_policy()

            self.assertFalse((fundamentals / "sn_warehouse_receipts.json").exists())
            self.assertFalse((fundamentals / "sn_tushare_warehouse_receipt.json").exists())
            self.assertFalse((out / "customer_predictions.json").exists())
            self.assertFalse((out / "model_registry" / "active_model.json").exists())

        self.assertFalse(policy["warehouse_receipt_available"])
        self.assertEqual(policy["inventory_missing_flag"], 1)
        self.assertEqual(policy["warehouse_data_quality_score"], 0.0)
        self.assertTrue(policy["no_fake_data"])
        self.assertEqual(policy["reason"], "tushare_fut_wsr_no_sn_rows")


if __name__ == "__main__":
    unittest.main()
