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

from sn_futures.services.tushare_futures_service import fetch_sn_warehouse_receipt


def _seed_probe_context(output_dir: Path) -> list[str]:
    days = [(date(2026, 1, 1) + timedelta(days=idx)).isoformat() for idx in range(6)]
    fundamentals = output_dir / "fundamentals"
    fundamentals.mkdir(parents=True, exist_ok=True)
    (output_dir / "sn_market_history.json").write_text(
        json.dumps({"sample": False, "history": [{"trade_date": day, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1} for day in days]}),
        encoding="utf-8",
    )
    (fundamentals / "sn_tushare_contracts.json").write_text(json.dumps({"rows": [{"ts_code": "SN2406.SHF", "contract": "SN2406"}]}), encoding="utf-8")
    return days


class StrictWsrClient:
    def __init__(self, days: list[str]) -> None:
        self.days = {day.replace("-", ""): idx for idx, day in enumerate(days)}
        self.calls: list[dict[str, object]] = []

    def fut_wsr(self, **kwargs: object) -> pd.DataFrame:
        self.calls.append(dict(kwargs))
        trade_date = str(kwargs.get("trade_date") or "")
        if kwargs.get("symbol") != "SN" or trade_date not in self.days:
            raise RuntimeError("参数校验失败, trade_date,symbol参数不能都为空")
        idx = self.days[trade_date]
        return pd.DataFrame(
            [
                {"trade_date": trade_date, "symbol": "SN", "product": "沪锡", "warehouse": "WH-A", "vol": 1000 + idx},
                {"trade_date": trade_date, "symbol": "CU", "product": "铜", "warehouse": "WH-CU", "vol": 9999},
            ]
        )


class TushareWsrRealContractTest(unittest.TestCase):
    def test_wsr_uses_sn_symbol_and_writes_standard_warehouse_receipt_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "TOKEN_123456789"}, clear=False):
            output_dir = Path(tmp) / "outputs"
            days = _seed_probe_context(output_dir)
            result = fetch_sn_warehouse_receipt(client=StrictWsrClient(days))
            payload = json.loads((output_dir / "fundamentals" / "sn_tushare_warehouse_receipt.json").read_text(encoding="utf-8"))

        self.assertTrue(result["success"])
        self.assertEqual(result["selected_params"]["symbol"], "SN")
        self.assertEqual(result["row_count"], 6)
        self.assertEqual(payload["row_count"], 6)
        self.assertEqual(payload["rows"][-1]["warehouse_receipt_delta_1w"], 5)
        for key in ("trade_date", "product", "warehouse", "warehouse_receipt", "warehouse_receipt_delta", "warehouse_receipt_delta_1w", "source"):
            self.assertIn(key, payload["rows"][0])
        self.assertNotIn("CU", json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
