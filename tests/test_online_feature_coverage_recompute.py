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


def _market_history(rows: int = 180) -> dict[str, object]:
    history = []
    for idx in range(rows):
        close = 200000 + idx * 10
        history.append(
            {
                "date": f"2025-01-{(idx % 28) + 1:02d}",
                "open": close - 20,
                "high": close + 50,
                "low": close - 60,
                "close": close,
                "volume": 1000 + idx,
            }
        )
    return {"sample": False, "history": history, "contract": "SN0"}


class OnlineFeatureCoverageRecomputeTest(unittest.TestCase):
    def test_alpha_fixture_can_raise_cross_market_readiness_without_lme_substitution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            outputs = Path(tmp) / "outputs"
            fundamentals = outputs / "fundamentals"
            _write_json(outputs / "sn_market_history.json", _market_history())
            _write_json(
                fundamentals / "sn_cross_market.json",
                {
                    "sample": False,
                    "rows": [
                        {"trade_date": "2025-01-01", "usd_cny": 7.1, "usd_cny_return": 0.01, "us10y": 4.2, "us10y_change": 0.02, "copper_global_proxy": 9800},
                        {"trade_date": "2025-01-02", "usd_cny": 7.2, "usd_cny_return": 0.014, "us10y": 4.1, "us10y_change": -0.1, "copper_global_proxy": 9900},
                    ],
                },
            )
            _write_json(fundamentals / "sn_lme_tin.json", {"sample": False, "rows": [], "missing_fields": ["lme_tin_close"]})
            report = build_online_feature_readiness_report()

        cross_market = next(row for row in report["factor_group_readiness"] if row["group"] == "cross_market")
        self.assertIn("usd_cny_return", report["available_fields"])
        self.assertIn("us10y_change", report["available_fields"])
        self.assertIn("lme_tin_close", cross_market["blocking_fields"])
        self.assertNotIn("lme_tin_close", report["available_fields"])

    def test_basis_inventory_coverage_does_not_improve_without_real_source(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_json(Path(tmp) / "outputs" / "sn_market_history.json", _market_history())
            report = build_online_feature_readiness_report()

        self.assertIn("spot_futures_basis", report["unavailable_fields"])
        self.assertIn("shfe_inventory", report["unavailable_fields"])
        self.assertFalse(report["research_readiness"]["can_train_basis_inventory_model"])


if __name__ == "__main__":
    unittest.main()
