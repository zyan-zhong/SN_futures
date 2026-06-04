from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.data_consistency_audit_service import build_data_consistency_report
from sn_futures.services.data_watermark_service import get_data_watermark_report, update_data_watermark


class NoStaleSampleAfterRealRefreshTest(unittest.TestCase):
    def test_real_market_data_forces_sample_mode_off_after_refresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            output.mkdir(parents=True, exist_ok=True)
            (output / "data_watermark.json").write_text(
                json.dumps({"sample_mode": True, "current_data_mode": "sample"}, ensure_ascii=False),
                encoding="utf-8",
            )
            (output / "sn_market_history.json").write_text(
                json.dumps({"history": [{"time": "2026-05-30", "open": 1, "high": 2, "low": 1, "close": 2, "volume": 10}]}),
                encoding="utf-8",
            )

            update_data_watermark("market", source="real-refresh")
            watermark = get_data_watermark_report()
            report = build_data_consistency_report()

        self.assertFalse(watermark["sample_mode"])
        self.assertEqual(watermark["current_data_mode"], "real")
        self.assertFalse(report["sample_mode_active"])
        self.assertTrue(report["checks"]["sample_retired_after_real_refresh"])


if __name__ == "__main__":
    unittest.main()
