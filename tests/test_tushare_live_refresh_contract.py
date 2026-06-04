from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.tushare_futures_service import refresh_tushare_futures_data


class SuccessfulTushareClient:
    def fut_basic(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"ts_code": "SN2406.SHF", "symbol": "SN2406", "exchange": "SHFE", "name": "沪锡2406"}])

    def trade_cal(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"cal_date": "20260102", "is_open": 1, "exchange": "SHFE"}])

    def fut_daily(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"trade_date": "20260102", "ts_code": "SN2406.SHF", "open": 1, "high": 2, "low": 1, "close": 2, "settle": 2, "vol": 3, "oi": 4},
                {"trade_date": "20260102", "ts_code": "CU2406.SHF", "open": 1, "high": 2, "low": 1, "close": 2, "settle": 2, "vol": 3, "oi": 4},
            ]
        )

    def fut_wsr(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": "20260102", "symbol": "SN", "product": "锡", "warehouse_receipt": 5}])

    def fut_settle(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": "20260102", "ts_code": "SN2406.SHF", "settle": 2, "margin_rate": 0.1, "fee_rate": 1.5}])

    def fut_holding(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": "20260102", "ts_code": "SN2406.SHF", "broker": "member", "rank": 1, "long_hld": 10, "short_hld": 8, "vol": 6}])


class PermissionDeniedTushareClient(SuccessfulTushareClient):
    def fut_daily(self, **_: object) -> pd.DataFrame:
        raise RuntimeError("抱歉，您没有访问该接口的权限")


class TushareLiveRefreshContractTest(unittest.TestCase):
    def test_successful_refresh_writes_safe_standard_tushare_outputs(self) -> None:
        token = "ENV_TUSHARE_TOKEN_123456789"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": token}, clear=False):
            result = refresh_tushare_futures_data(client=SuccessfulTushareClient(), force=True)
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            status = json.loads((fundamentals / "tushare_provider_status.json").read_text(encoding="utf-8"))
            output_payloads = {
                filename: json.loads((fundamentals / filename).read_text(encoding="utf-8"))
                for filename in (
                    "sn_tushare_daily.json",
                    "sn_tushare_warehouse_receipt.json",
                    "sn_tushare_settlement.json",
                    "sn_tushare_holding.json",
                    "sn_tushare_contracts.json",
                )
            }

        self.assertEqual(result["status"], "success")
        self.assertEqual(status["source"], "tushare")
        self.assertEqual(status["config_source"], "env")
        self.assertFalse(status["active_updated"])
        self.assertFalse(status["customer_prediction_generated"])
        for payload in output_payloads.values():
            self.assertEqual(payload["source"], "tushare")
            self.assertIn("generated_at", payload)
            self.assertGreaterEqual(int(payload.get("row_count") or 0), 1)
            self.assertIn("date_start", payload)
            self.assertIn("date_end", payload)
            self.assertNotIn(token, json.dumps(payload, ensure_ascii=False))
            self.assertNotIn("CU2406", json.dumps(payload, ensure_ascii=False))

    def test_permission_denied_status_is_explicit_and_does_not_fake_daily_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "ENV_TUSHARE_TOKEN_123456789"}, clear=False):
            result = refresh_tushare_futures_data(client=PermissionDeniedTushareClient(), force=True)
            fundamentals = Path(tmp) / "outputs" / "fundamentals"

        self.assertEqual(result["results"]["tushare_daily"]["status"], "permission_denied")
        self.assertFalse((fundamentals / "sn_tushare_daily.json").exists())
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
