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


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


class OnlineFeatureReadinessServiceTest(unittest.TestCase):
    def test_empty_online_sources_do_not_require_customer_upload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            os.environ.pop("SN_ALPHA_VANTAGE_KEY", None)
            report = build_online_feature_readiness_report()

        self.assertFalse(report["client_upload_required"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])
        self.assertFalse(report["baseline_used"])
        cross_fields = [row for row in report["field_readiness"] if row["field"] == "usd_cny"]
        self.assertIn(cross_fields[0]["status"], {"key_missing", "unavailable"})

    def test_cross_market_fields_are_available_from_real_online_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            _write_json(
                fundamentals / "sn_cross_market.json",
                {
                    "sample": False,
                    "rows": [
                        {"trade_date": "2026-01-01", "usd_cny": 7.1, "usd_cny_return": 0.01, "us10y": 4.2, "us10y_change": 0.02},
                        {"trade_date": "2026-01-02", "usd_cny": 7.2, "usd_cny_return": 0.014, "us10y": 4.1, "us10y_change": -0.1},
                    ],
                },
            )
            _write_json(fundamentals / "fx_macro_provider_status.json", {"status": "success", "row_count": 2})
            report = build_online_feature_readiness_report()

        available = set(report["available_fields"])
        self.assertIn("usd_cny", available)
        self.assertIn("us10y", available)
        self.assertFalse(report["client_upload_required"])

    def test_lme_and_basis_inventory_are_not_faked_when_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            fundamentals = Path(tmp) / "outputs" / "fundamentals"
            _write_json(fundamentals / "sn_lme_tin.json", {"sample": False, "rows": [], "missing_fields": ["lme_tin_close"]})
            _write_json(fundamentals / "lme_tin_provider_status.json", {"status": "paid_or_unavailable"})
            report = build_online_feature_readiness_report()

        statuses = {row["field"]: row["status"] for row in report["field_readiness"]}
        self.assertNotEqual(statuses["lme_tin_close"], "available")
        self.assertNotEqual(statuses["spot_futures_basis"], "available")
        self.assertNotEqual(statuses["shfe_inventory"], "available")
        self.assertIn("lme_tin_close", report["unavailable_fields"])


if __name__ == "__main__":
    unittest.main()
