from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.online_feature_readiness_service import build_online_feature_readiness_report


class CrossMarketFeatureCoverageAfterKeyTest(unittest.TestCase):
    def test_cross_market_readiness_improves_after_alpha_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            fundamentals.mkdir(parents=True, exist_ok=True)
            (fundamentals / "sn_cross_market.json").write_text(
                json.dumps({"rows": [{"trade_date": "2026-05-25", "usd_cny": 7.2, "us10y": 4.1, "copper_global_proxy": 9500}]}),
                encoding="utf-8",
            )
            (fundamentals / "fx_macro_provider_status.json").write_text(json.dumps({"status": "success", "row_count": 1}), encoding="utf-8")
            report = build_online_feature_readiness_report()

        self.assertIn("usd_cny", report["available_fields"])
        self.assertIn("us10y", report["available_fields"])
        self.assertIn("copper_global_proxy", report["available_fields"])
        self.assertNotIn("lme_tin_close", report["available_fields"])


if __name__ == "__main__":
    unittest.main()

