from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v5_service import build_feature_store_v6
from sn_futures.services.tushare_futures_service import refresh_tushare_futures_data


def _write_market_history(output_dir: Path) -> list[str]:
    start = date(2026, 1, 1)
    days = [(start + timedelta(days=idx)).isoformat() for idx in range(20)]
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "sn_market_history.json").write_text(
        json.dumps(
            {
                "sample": False,
                "history": [
                    {
                        "trade_date": day,
                        "open": 210000 + idx,
                        "high": 210100 + idx,
                        "low": 209900 + idx,
                        "close": 210050 + idx,
                        "volume": 1000 + idx,
                    }
                    for idx, day in enumerate(days)
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return days


class AuxiliaryCoverageClient:
    def __init__(self, days: list[str]) -> None:
        self.days = {day.replace("-", ""): idx for idx, day in enumerate(days)}

    def fut_basic(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"ts_code": "SN2406.SHF", "symbol": "SN2406", "exchange": "SHFE", "name": "沪锡2406"}])

    def trade_cal(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"cal_date": day, "is_open": 1, "exchange": "SHFE"} for day in self.days])

    def fut_daily(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"trade_date": day, "ts_code": "SN2406.SHF", "open": 210000 + idx, "high": 210100 + idx, "low": 209900 + idx, "close": 210050 + idx, "settle": 210020 + idx, "vol": 1000 + idx, "oi": 3000 + idx}
                for day, idx in self.days.items()
            ]
        )

    def fut_wsr(self, **kwargs: object) -> pd.DataFrame:
        trade_date = str(kwargs.get("trade_date") or "")
        if kwargs.get("symbol") != "SN" or trade_date not in self.days:
            raise RuntimeError("参数校验失败, trade_date,symbol参数不能都为空")
        idx = self.days[trade_date]
        return pd.DataFrame([{"trade_date": trade_date, "symbol": "SN", "product": "沪锡", "warehouse": "WH-A", "vol": 1200 + idx}])

    def fut_settle(self, **kwargs: object) -> pd.DataFrame:
        trade_date = str(kwargs.get("trade_date") or "")
        if kwargs.get("ts_code") != "SN2406.SHF" or trade_date not in self.days:
            raise RuntimeError("参数校验失败, trade_date,ts_code不能都为空")
        idx = self.days[trade_date]
        return pd.DataFrame([{"trade_date": trade_date, "ts_code": "SN2406.SHF", "settle": 210020 + idx, "trade_fee": 3.0, "trade_fee_rate": 0.0002, "long_margin_rate": 0.12, "short_margin_rate": 0.13, "offset_today_fee": 1.5}])

    def fut_holding(self, **kwargs: object) -> pd.DataFrame:
        trade_date = str(kwargs.get("trade_date") or "")
        if kwargs.get("symbol") != "SN" or trade_date not in self.days:
            raise RuntimeError("参数校验失败, trade_date,symbol参数不能都为空")
        idx = self.days[trade_date]
        return pd.DataFrame([{"trade_date": trade_date, "symbol": "SN", "broker": "member-a", "rank": 1, "long_hld": 80 + idx, "short_hld": 40 + idx, "long_chg": 2, "short_chg": -1}])


class TushareFeatureCoverageAfterAuxiliaryTest(unittest.TestCase):
    def test_auxiliary_tushare_fields_enter_feature_store_v6_manifest_without_model_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "TOKEN_123456789"}, clear=False):
            output_dir = Path(tmp) / "outputs"
            days = _write_market_history(output_dir)
            refresh = refresh_tushare_futures_data(client=AuxiliaryCoverageClient(days), force=True)
            manifest = build_feature_store_v6()

        self.assertEqual(refresh["status"], "success")
        for field in ("warehouse_receipt_delta_1w", "settlement", "trading_fee", "long_margin_rate", "short_margin_rate", "member_net_position"):
            self.assertIn(field, manifest["usable_fields"])
            self.assertEqual(manifest["field_sources"][field], "tushare")
        self.assertTrue(manifest["tushare_wsr_used"])
        self.assertTrue(manifest["tushare_settle_used"])
        self.assertTrue(manifest["tushare_holding_used"])
        self.assertFalse(manifest["failed_subinterfaces"])
        self.assertIn("fut_wsr", manifest["selected_params"])
        self.assertFalse(manifest["active_model_written"])
        self.assertFalse(manifest["customer_prediction_generated"])
        self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())
        self.assertFalse((Path(tmp) / "outputs" / "customer_predictions.json").exists())


if __name__ == "__main__":
    unittest.main()
