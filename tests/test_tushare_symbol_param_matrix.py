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

from sn_futures.services.tushare_param_probe_service import build_tushare_param_probe_report


class ParamMatrixClient:
    def __init__(self) -> None:
        self.calls: dict[str, list[dict[str, object]]] = {"fut_wsr": [], "fut_settle": [], "fut_holding": []}

    def fut_wsr(self, **kwargs: object) -> pd.DataFrame:
        self.calls["fut_wsr"].append(dict(kwargs))
        if kwargs.get("symbol") == "SN" and kwargs.get("trade_date") == "20260102":
            return pd.DataFrame([{"trade_date": "20260102", "symbol": "SN", "warehouse": "WH-A", "vol": 1200}])
        raise RuntimeError("parameter mismatch")

    def fut_settle(self, **kwargs: object) -> pd.DataFrame:
        self.calls["fut_settle"].append(dict(kwargs))
        if kwargs.get("ts_code") == "SN2406.SHF" and kwargs.get("trade_date") == "20260102":
            return pd.DataFrame([{"trade_date": "20260102", "ts_code": "SN2406.SHF", "settle": 210300}])
        raise RuntimeError("parameter mismatch")

    def fut_holding(self, **kwargs: object) -> pd.DataFrame:
        self.calls["fut_holding"].append(dict(kwargs))
        if kwargs.get("symbol") == "SN" and kwargs.get("trade_date") == "20260102":
            return pd.DataFrame([{"trade_date": "20260102", "symbol": "SN", "broker": "member-a", "long_hld": 80, "short_hld": 40}])
        raise RuntimeError("parameter mismatch")


class TushareSymbolParamMatrixTest(unittest.TestCase):
    def test_auxiliary_interfaces_probe_real_sn_parameter_shapes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "TOKEN_123456789"}, clear=False):
            output_dir = Path(tmp) / "outputs"
            fundamentals = output_dir / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            (output_dir / "sn_market_history.json").write_text(
                json.dumps({"sample": False, "history": [{"trade_date": "2026-01-02", "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1}]}),
                encoding="utf-8",
            )
            (fundamentals / "sn_tushare_contracts.json").write_text(
                json.dumps({"rows": [{"trade_date": "2026-01-02", "contract": "SN2406", "ts_code": "SN2406.SHF"}]}),
                encoding="utf-8",
            )
            client = ParamMatrixClient()

            report = build_tushare_param_probe_report(client=client, api_names=["fut_wsr", "fut_settle", "fut_holding"])
            saved = json.loads((fundamentals / "tushare_param_probe_report.json").read_text(encoding="utf-8"))

        self.assertEqual(report["results"]["fut_wsr"]["status"], "success")
        self.assertEqual(report["results"]["fut_wsr"]["selected_params"]["symbol"], "SN")
        self.assertEqual(report["results"]["fut_wsr"]["selected_params"]["trade_date"], "20260102")
        self.assertNotIn("ts_code", report["results"]["fut_wsr"]["selected_params"])
        self.assertEqual(report["results"]["fut_settle"]["selected_params"]["ts_code"], "SN2406.SHF")
        self.assertEqual(report["results"]["fut_settle"]["selected_params"]["trade_date"], "20260102")
        self.assertEqual(report["results"]["fut_holding"]["selected_params"]["symbol"], "SN")
        self.assertEqual(saved["results"]["fut_holding"]["row_count"], 1)
        self.assertTrue(client.calls["fut_wsr"])
        self.assertTrue(client.calls["fut_settle"])
        self.assertTrue(client.calls["fut_holding"])


if __name__ == "__main__":
    unittest.main()
