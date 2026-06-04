from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.chart_payload_service import build_price_chart_payload


class ChartMatchesLatestDataTest(unittest.TestCase):
    def test_price_chart_payload_exposes_latest_market_history_date(self) -> None:
        rows = [
            {"time": "2026-05-28", "open": 1, "high": 2, "low": 1, "close": 2, "volume": 10},
            {"time": "2026-05-29", "open": 2, "high": 3, "low": 2, "close": 3, "volume": 11},
            {"time": "2026-05-30", "open": 3, "high": 4, "low": 3, "close": 4, "volume": 12},
        ]
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            output.mkdir(parents=True, exist_ok=True)
            (output / "sn_market_history.json").write_text(json.dumps({"history": rows}), encoding="utf-8")
            payload = build_price_chart_payload(max_points=100)

        self.assertEqual(payload["latest_date"], "2026-05-30")
        self.assertEqual(payload["points"][-1]["time"], "2026-05-30")
        self.assertEqual(payload["data_freshness"]["latest_date"], "2026-05-30")


if __name__ == "__main__":
    unittest.main()
