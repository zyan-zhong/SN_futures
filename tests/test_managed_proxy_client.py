from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_data_proxy_service import refresh_managed_data_proxy, test_managed_proxy_connection


class FakeManagedClient:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, str]]] = []

    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        self.calls.append((path, headers))
        if path == "/api/sn/status":
            return {"status": "success", "service": "mock-managed-proxy"}
        if path.startswith("/api/sn/fundamentals/history"):
            return {
                "status": "success",
                "rows": [
                    {
                        "trade_date": "2026-05-20",
                        "symbol": "SN",
                        "spot_price": 270000,
                        "spot_futures_basis": 800,
                        "shfe_inventory": 8000,
                        "lme_tin_close": 33500,
                        "near_contract": "SN2606",
                        "far_contract": "SN2607",
                        "near_contract_close": 269200,
                        "far_contract_close": 268600,
                        "near_open_interest": 42000,
                        "far_open_interest": 36000,
                        "main_contract": "SN2606",
                        "main_contract_switch_flag": 0,
                    }
                ],
            }
        raise AssertionError(path)


class ManagedProxyClientTest(unittest.TestCase):
    def test_status_uses_license_header_and_never_returns_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            os.environ["SN_MANAGED_DATA_PROXY_TOKEN"] = "managed-secret-token"
            os.environ["SN_MANAGED_DATA_PROXY_URL"] = "http://managed.example"
            client = FakeManagedClient()

            status = test_managed_proxy_connection(client=client)

            self.assertTrue(status["configured"])
            self.assertEqual(status["status"], "success")
            self.assertNotIn("managed-secret-token", json.dumps(status))
            self.assertEqual(client.calls[0][1]["X-SN-License-Token"], "managed-secret-token")

    def test_refresh_writes_managed_fundamental_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            os.environ["SN_MANAGED_DATA_PROXY_TOKEN"] = "managed-secret-token"
            os.environ["SN_MANAGED_DATA_PROXY_URL"] = "http://managed.example"
            result = refresh_managed_data_proxy(client=FakeManagedClient())

            self.assertTrue(result["success"])
            out = Path(tmp) / "outputs" / "fundamentals"
            self.assertTrue((out / "managed_fundamentals.json").exists())
            self.assertTrue((out / "managed_proxy_status.json").exists())
            rows = json.loads((out / "managed_fundamentals.json").read_text(encoding="utf-8"))["rows"]
            self.assertEqual(rows[0]["trade_date"], "2026-05-20")
            self.assertIn("last_good_managed_fundamentals.json", " ".join(result["output_files"]))


if __name__ == "__main__":
    unittest.main()
