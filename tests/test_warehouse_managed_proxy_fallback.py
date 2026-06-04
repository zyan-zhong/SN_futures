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


class WarehouseManagedProxyFallbackTest(unittest.TestCase):
    def test_managed_proxy_real_sn_warehouse_rows_are_preferred_over_missing_tushare_wsr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            fundamentals = out / "fundamentals"
            _write_json(
                fundamentals / "tushare_provider_status.json",
                {"results": {"tushare_warehouse": {"status": "no_sn_rows", "row_count": 0}}},
            )
            _write_json(
                fundamentals / "managed_fundamentals.json",
                {
                    "source": "managed_data_proxy",
                    "rows": [
                        {"trade_date": "2026-01-02", "product": "AL", "shfe_warehouse_receipt": 9999},
                        {"trade_date": "2026-01-02", "product": "SN", "shfe_warehouse_receipt": 1200},
                        {"trade_date": "2026-01-03", "symbol": "SN2601", "shfe_warehouse_receipt": 1215},
                    ],
                },
            )

            policy = build_warehouse_missing_policy()
            warehouse_path = fundamentals / "sn_warehouse_receipts.json"
            self.assertTrue(warehouse_path.exists())
            payload = json.loads(warehouse_path.read_text(encoding="utf-8"))

        self.assertTrue(policy["warehouse_receipt_available"])
        self.assertEqual(policy["source"], "managed_proxy")
        self.assertEqual(policy["row_count"], 2)
        self.assertEqual(policy["inventory_missing_flag"], 0)
        self.assertTrue(policy["no_fake_data"])
        self.assertEqual([row["product"] for row in payload["rows"]], ["SN", "SN"])
        self.assertEqual([row["warehouse_receipt"] for row in payload["rows"]], [1200.0, 1215.0])
        self.assertNotIn(9999.0, [row["warehouse_receipt"] for row in payload["rows"]])


if __name__ == "__main__":
    unittest.main()
