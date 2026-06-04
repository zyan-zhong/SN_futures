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

from sn_futures.services.settings_service import get_key_diagnostics
from sn_futures.services.tushare_futures_service import refresh_tushare_futures_data


class MinimalTushareClient:
    def fut_basic(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"ts_code": "SN2406.SHF", "symbol": "SN2406", "exchange": "SHFE", "name": "沪锡2406"}])

    def trade_cal(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"cal_date": "20260102", "is_open": 1, "exchange": "SHFE"}])

    def fut_daily(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": "20260102", "ts_code": "SN2406.SHF", "close": 2, "settle": 2, "vol": 3, "oi": 4}])

    def fut_wsr(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": "20260102", "symbol": "SN", "product": "锡", "warehouse_receipt": 5}])

    def fut_settle(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": "20260102", "ts_code": "SN2406.SHF", "settle": 2}])

    def fut_holding(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": "20260102", "ts_code": "SN2406.SHF", "long_hld": 10, "short_hld": 8}])


class TushareNoSecretLeakageTest(unittest.TestCase):
    def test_refresh_and_diagnostics_do_not_write_or_return_complete_tushare_token(self) -> None:
        token = "ENV_TUSHARE_TOKEN_123456789"
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": token}, clear=False):
            result = refresh_tushare_futures_data(client=MinimalTushareClient(), force=True)
            diagnostics = get_key_diagnostics()
            output_dir = Path(tmp) / "outputs"
            payloads = [result, diagnostics]
            for path in (output_dir / "fundamentals").glob("*.json"):
                payloads.append(json.loads(path.read_text(encoding="utf-8")))

        self.assertNotIn(token, json.dumps(payloads, ensure_ascii=False))
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
