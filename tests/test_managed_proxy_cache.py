from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_data_proxy_service import refresh_managed_data_proxy


class FailingClient:
    def get_json(self, path: str, headers: dict[str, str]) -> dict:
        raise RuntimeError("network failed with token should be masked")


class ManagedProxyCacheTest(unittest.TestCase):
    def test_failure_uses_last_good_cache_without_overwriting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            os.environ["SN_MANAGED_DATA_PROXY_TOKEN"] = "managed-cache-token"
            os.environ["SN_MANAGED_DATA_PROXY_URL"] = "http://managed.example"
            out = Path(tmp) / "outputs" / "fundamentals"
            out.mkdir(parents=True, exist_ok=True)
            cached = {
                "rows": [
                    {
                        "trade_date": "2026-05-20",
                        "symbol": "SN",
                        "spot_price": 270000,
                        "shfe_inventory": 8000,
                    }
                ]
            }
            (out / "managed_fundamentals.json").write_text(json.dumps(cached), encoding="utf-8")
            (out / "last_good_managed_fundamentals.json").write_text(json.dumps(cached), encoding="utf-8")

            result = refresh_managed_data_proxy(client=FailingClient())

            self.assertEqual(result["status"], "using_cache")
            self.assertTrue(result["from_cache"])
            after = json.loads((out / "managed_fundamentals.json").read_text(encoding="utf-8"))
            self.assertEqual(after["rows"][0]["spot_price"], 270000)
            self.assertNotIn("managed-cache-token", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
