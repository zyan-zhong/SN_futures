from __future__ import annotations

import json
import os
import tempfile
import unittest
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v5_service import build_feature_store_v5


def _write(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


class FeatureStoreV5SourceQualityTest(unittest.TestCase):
    def test_manifest_records_source_quality_and_mock_flag(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            os.environ["SN_INSIGHT_DATA_DIR"] = tmp
            out = Path(tmp) / "outputs"
            start = date(2026, 1, 1)
            market = [{"trade_date": (start + timedelta(days=i)).isoformat(), "open": 1 + i, "high": 2 + i, "low": 1 + i, "close": 2 + i, "volume": 100 + i} for i in range(70)]
            _write(out / "sn_market_history.json", {"history": market})
            _write(out / "fundamentals" / "managed_fundamentals.json", {"mock_data_used": True, "rows": [{"trade_date": row["trade_date"], "symbol": "SN", "spot_price": 250000 + i} for i, row in enumerate(market)]})

            manifest = build_feature_store_v5()

            self.assertTrue(manifest["mock_data_used"])
            self.assertIn("managed_proxy", manifest["source_quality"])
            self.assertEqual(manifest["source_quality"]["managed_proxy"]["status"], "mock_data")
            self.assertIn("spot_price", manifest["excluded_fields"] + manifest["usable_fields"])


if __name__ == "__main__":
    unittest.main()
