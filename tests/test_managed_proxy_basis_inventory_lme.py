from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_data_proxy_service import (
    managed_fundamentals_schema,
    normalize_managed_fundamental_rows,
    refresh_managed_data_proxy,
)


class FakeManagedFundamentalsClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        assert path.startswith("/api/sn/fundamentals/history?")
        assert headers.get("X-SN-License-Token") == "managed-real-token"
        return {
            "status": "success",
            "rows": [
                {
                    "trade_date": "2026-05-20",
                    "symbol": "SN2606",
                    "spot_price": "270000",
                    "spot_premium": "1200",
                    "spot_futures_basis": "800",
                    "shfe_inventory": "8000",
                    "shfe_warehouse_receipt": "4100",
                    "lme_tin_close": "33500",
                    "lme_inventory": "4700",
                    "near_contract": "SN2606",
                    "far_contract": "SN2607",
                    "near_contract_close": "269200",
                    "far_contract_close": "268600",
                    "near_open_interest": "42000",
                    "far_open_interest": "36000",
                    "main_contract": "SN2606",
                }
            ],
        }


class ManagedProxyBasisInventoryLmeTest(unittest.TestCase):
    def test_schema_declares_basis_inventory_warehouse_and_lme_fields(self) -> None:
        schema = managed_fundamentals_schema()

        self.assertEqual(schema["provider_id"], "managed_data_proxy")
        self.assertTrue(schema["no_fake_data"])
        for field in (
            "shfe_warehouse_receipt",
            "shfe_inventory",
            "spot_price",
            "spot_premium",
            "spot_futures_basis",
            "lme_tin_close",
            "lme_inventory",
        ):
            self.assertIn(field, schema["required_research_fields"])
        self.assertEqual(schema["groups"]["warehouse"], ["shfe_warehouse_receipt"])
        self.assertIn("spot_futures_basis", schema["groups"]["basis"])
        self.assertIn("lme_tin_close", schema["groups"]["lme"])

    def test_refresh_writes_real_managed_fundamental_rows_without_exposing_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            os.environ["SN_MANAGED_DATA_PROXY_TOKEN"] = "managed-real-token"
            os.environ["SN_MANAGED_DATA_PROXY_URL"] = "https://managed.example"
            try:
                result = refresh_managed_data_proxy(client=FakeManagedFundamentalsClient())
                out = Path(tmp) / "outputs" / "fundamentals"
                payload = json.loads((out / "managed_fundamentals.json").read_text(encoding="utf-8"))
            finally:
                os.environ.pop("SN_INSIGHT_DATA_DIR", None)
                os.environ.pop("SN_MANAGED_DATA_PROXY_TOKEN", None)
                os.environ.pop("SN_MANAGED_DATA_PROXY_URL", None)

        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "success")
        self.assertIn("managed_schema", result)
        self.assertIn("shfe_warehouse_receipt", result["managed_schema"]["required_research_fields"])
        self.assertNotIn("managed-real-token", json.dumps(result, ensure_ascii=False))
        row = payload["rows"][0]
        self.assertEqual(row["symbol"], "SN2606")
        self.assertAlmostEqual(row["spot_price"], 270000.0)
        self.assertAlmostEqual(row["lme_inventory"], 4700.0)

    def test_normalization_rejects_other_metals_instead_of_relabelling_as_tin(self) -> None:
        rows = normalize_managed_fundamental_rows(
            [
                {"trade_date": "2026-05-20", "symbol": "CU2606", "shfe_warehouse_receipt": 1000},
                {"trade_date": "2026-05-20", "symbol": "SN2606", "shfe_warehouse_receipt": 4100},
            ]
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["symbol"], "SN2606")


if __name__ == "__main__":
    unittest.main()
