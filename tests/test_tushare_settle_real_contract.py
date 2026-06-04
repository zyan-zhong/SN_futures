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

from sn_futures.services.tushare_futures_service import fetch_sn_settlement


def _seed_probe_context(output_dir: Path) -> list[str]:
    days = [(date(2026, 1, 1) + timedelta(days=idx)).isoformat() for idx in range(3)]
    fundamentals = output_dir / "fundamentals"
    fundamentals.mkdir(parents=True, exist_ok=True)
    (output_dir / "sn_market_history.json").write_text(
        json.dumps({"sample": False, "history": [{"trade_date": day, "open": 1, "high": 1, "low": 1, "close": 1, "volume": 1} for day in days]}),
        encoding="utf-8",
    )
    (fundamentals / "sn_tushare_contracts.json").write_text(json.dumps({"rows": [{"ts_code": "SN2406.SHF", "contract": "SN2406"}]}), encoding="utf-8")
    return days


class StrictSettleClient:
    def __init__(self, days: list[str]) -> None:
        self.days = {day.replace("-", ""): idx for idx, day in enumerate(days)}

    def fut_settle(self, **kwargs: object) -> pd.DataFrame:
        trade_date = str(kwargs.get("trade_date") or "")
        if kwargs.get("ts_code") != "SN2406.SHF" or trade_date not in self.days:
            raise RuntimeError("参数校验失败, trade_date,ts_code不能都为空")
        idx = self.days[trade_date]
        return pd.DataFrame(
            [
                {
                    "trade_date": trade_date,
                    "ts_code": "SN2406.SHF",
                    "settle": 210000 + idx,
                    "trade_fee": 3.0,
                    "trade_fee_rate": 0.0002,
                    "long_margin_rate": 0.12,
                    "short_margin_rate": 0.13,
                    "offset_today_fee": 1.5,
                },
                {"trade_date": trade_date, "ts_code": "CU2406.SHF", "settle": 70000},
            ]
        )


class TushareSettleRealContractTest(unittest.TestCase):
    def test_settle_uses_shed_contract_and_writes_fee_margin_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "TOKEN_123456789"}, clear=False):
            output_dir = Path(tmp) / "outputs"
            days = _seed_probe_context(output_dir)
            result = fetch_sn_settlement(client=StrictSettleClient(days))
            payload = json.loads((output_dir / "fundamentals" / "sn_tushare_settlement.json").read_text(encoding="utf-8"))

        self.assertTrue(result["success"])
        self.assertEqual(result["selected_params"]["ts_code"], "SN2406.SHF")
        self.assertEqual(payload["row_count"], 3)
        for key in ("trade_date", "contract", "settlement", "trading_fee_rate", "trading_fee", "long_margin_rate", "short_margin_rate", "offset_today_fee", "source"):
            self.assertIn(key, payload["rows"][0])
        self.assertEqual(payload["rows"][0]["trading_fee"], 3.0)
        self.assertNotIn("CU2406", json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
