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

from sn_futures.services.tushare_futures_service import fetch_sn_holding


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


class StrictHoldingClient:
    def __init__(self, days: list[str]) -> None:
        self.days = {day.replace("-", ""): idx for idx, day in enumerate(days)}

    def fut_holding(self, **kwargs: object) -> pd.DataFrame:
        trade_date = str(kwargs.get("trade_date") or "")
        if kwargs.get("symbol") != "SN" or trade_date not in self.days:
            raise RuntimeError("参数校验失败, trade_date,symbol参数不能都为空")
        idx = self.days[trade_date]
        return pd.DataFrame(
            [
                {"trade_date": trade_date, "symbol": "SN", "broker": "member-a", "rank": 1, "long_hld": 80 + idx, "short_hld": 40 + idx, "long_chg": 2, "short_chg": -1},
                {"trade_date": trade_date, "symbol": "CU", "broker": "member-cu", "rank": 1, "long_hld": 800, "short_hld": 700},
            ]
        )


class TushareHoldingRealContractTest(unittest.TestCase):
    def test_holding_uses_sn_symbol_and_writes_member_net_position(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp, "SN_TUSHARE_TOKEN": "TOKEN_123456789"}, clear=False):
            output_dir = Path(tmp) / "outputs"
            days = _seed_probe_context(output_dir)
            result = fetch_sn_holding(client=StrictHoldingClient(days))
            payload = json.loads((output_dir / "fundamentals" / "sn_tushare_holding.json").read_text(encoding="utf-8"))

        self.assertTrue(result["success"])
        self.assertEqual(result["selected_params"]["symbol"], "SN")
        self.assertEqual(payload["row_count"], 3)
        for key in ("trade_date", "contract_or_product", "member_name", "long_position", "short_position", "member_net_position", "long_change", "short_change", "source"):
            self.assertIn(key, payload["rows"][0])
        self.assertEqual(payload["rows"][0]["member_net_position"], 40)
        self.assertNotIn("member-cu", json.dumps(payload, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
