from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v11_service import run_managed_proxy_v11_real_loop


class FakeManagedFundamentalsClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        assert headers.get("X-SN-License-Token")
        assert path.startswith("/api/sn/fundamentals/history")
        rows = []
        for day in range(1, 32):
            rows.append(
                {
                    "trade_date": f"2026-05-{day:02d}",
                    "symbol": "SN2606",
                    "spot_price": 250000 + day,
                    "spot_premium": 100 + day,
                    "spot_futures_basis": 500 + day,
                    "shfe_inventory": 8000 + day,
                    "shfe_warehouse_receipt": 4100 + day,
                    "lme_tin_close": 33500 + day,
                    "lme_inventory": 4700 + day,
                    "near_contract": "SN2606",
                    "far_contract": "SN2607",
                    "near_contract_close": 249000 + day,
                    "far_contract_close": 248500 + day,
                    "near_open_interest": 42000 + day,
                    "far_open_interest": 36000 + day,
                    "main_contract": "SN2606",
                }
            )
        return {"status": "success", "rows": rows}


def _write_market_history(output_dir: Path) -> None:
    history = [
        {
            "trade_date": f"2026-05-{day:02d}",
            "open": 249000 + day,
            "high": 251000 + day,
            "low": 248000 + day,
            "close": 250000 + day,
            "volume": 1000 + day,
            "open_interest": 20000 + day,
        }
        for day in range(1, 32)
    ]
    path = output_dir / "sn_market_history.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"history": history}), encoding="utf-8")


class ManagedProxyMinimalRealLoopV11Test(unittest.TestCase):
    def test_disabled_managed_proxy_writes_blocked_v11_without_fake_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            os.environ.pop("SN_MANAGED_DATA_PROXY_TOKEN", None)
            os.environ.pop("SN_MANAGED_DATA_PROXY_URL", None)
            os.environ.pop("SN_MANAGED_DATA_PROXY_ENABLED", None)
            try:
                _write_market_history(Path(tmp) / "outputs")
                result = run_managed_proxy_v11_real_loop(force=True)
            finally:
                os.environ.pop("SN_INSIGHT_DATA_DIR", None)

        self.assertEqual(result["managed_proxy_status"]["status"], "disabled")
        self.assertFalse(result["v11_readiness"]["ready"])
        self.assertIn("managed_proxy_disabled", result["v11_readiness"]["blocking_reasons"])
        self.assertTrue(result["no_fake_data"])
        self.assertFalse(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_real_managed_proxy_rows_make_v11_ready_without_secret_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            os.environ["SN_MANAGED_DATA_PROXY_TOKEN"] = "managed-real-token"
            os.environ["SN_MANAGED_DATA_PROXY_URL"] = "https://managed.example"
            try:
                output_dir = Path(tmp) / "outputs"
                _write_market_history(output_dir)
                result = run_managed_proxy_v11_real_loop(force=True, client=FakeManagedFundamentalsClient())
                store_exists = Path(result["feature_store_v11"]["feature_store_path"]).exists()
            finally:
                os.environ.pop("SN_INSIGHT_DATA_DIR", None)
                os.environ.pop("SN_MANAGED_DATA_PROXY_TOKEN", None)
                os.environ.pop("SN_MANAGED_DATA_PROXY_URL", None)

        serialized = json.dumps(result, ensure_ascii=False)
        self.assertNotIn("managed-real-token", serialized)
        self.assertEqual(result["managed_proxy_status"]["status"], "success")
        self.assertTrue(result["v11_readiness"]["ready"])
        self.assertEqual(result["missing_fields"], [])
        for field in (
            "spot_price",
            "spot_premium",
            "spot_futures_basis",
            "shfe_inventory",
            "shfe_warehouse_receipt",
            "lme_tin_close",
            "lme_inventory",
            "near_contract_close",
            "far_contract_close",
        ):
            self.assertIn(field, result["v11_readiness"]["available_fields"])
        self.assertTrue(store_exists)
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
