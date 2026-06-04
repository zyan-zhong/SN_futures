from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.feature_store_v5_service import build_feature_store_v5
from sn_futures.services.real_data_coverage_validation_service import build_candidate_v6_readiness, get_candidate_v6_readiness


def _coverage(groups: dict[str, float]) -> dict[str, object]:
    return {
        "sample_count": 90,
        "groups": [
            {"group": group, "coverage_rate": rate, "feature_count": 10, "available_feature_count": int(rate * 10)}
            for group, rate in groups.items()
        ],
        "usable_feature_cols": [],
    }


class CandidateV6ReadinessAfterTushareTokenTest(unittest.TestCase):
    def test_readiness_can_become_ready_from_real_tushare_incremental_fields(self) -> None:
        readiness = build_candidate_v6_readiness(
            coverage_before=_coverage({"raw_market": 0.833333, "inventory": 0.0, "term_structure": 0.166667}),
            coverage_after=_coverage({"raw_market": 1.0, "inventory": 0.25, "term_structure": 0.166667}),
            feature_store_v5={
                "status": "success",
                "usable_fields": ["open_interest", "settlement", "warehouse_receipt_delta_1w", "member_net_position"],
                "tushare_used": True,
                "tushare_fields": ["open_interest", "settlement", "warehouse_receipt_delta_1w", "member_net_position"],
                "sample_data_used": False,
                "mock_data_used": False,
                "baseline_used": False,
                "no_lookahead_pass": True,
                "leakage_check_pass": True,
            },
        )

        self.assertEqual(readiness["status"], "ready")
        self.assertIn("raw_market", readiness["new_factor_groups"])
        self.assertIn("inventory", readiness["new_factor_groups"])
        self.assertIn("open_interest", readiness["new_fields"])
        self.assertIn("warehouse_receipt_delta_1w", readiness["new_fields"])
        self.assertFalse(readiness["training_invoked"])

    def test_endpoint_recomputes_when_feature_store_is_newer_than_stale_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output_dir = Path(tmp) / "outputs"
            fundamentals = output_dir / "fundamentals"
            diagnostics = output_dir / "diagnostics"
            fundamentals.mkdir(parents=True, exist_ok=True)
            diagnostics.mkdir(parents=True, exist_ok=True)
            start = date(2026, 1, 1)
            days = [(start + timedelta(days=idx)).isoformat() for idx in range(90)]
            (output_dir / "sn_market_history.json").write_text(
                json.dumps(
                    {
                        "sample": False,
                        "history": [
                            {"trade_date": day, "open": 210000 + idx, "high": 210100 + idx, "low": 209900 + idx, "close": 210050 + idx, "volume": 1000 + idx}
                            for idx, day in enumerate(days)
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (fundamentals / "sn_tushare_daily.json").write_text(
                json.dumps(
                    {
                        "source": "tushare",
                        "status": "success",
                        "row_count": len(days),
                        "rows": [
                            {
                                "trade_date": day,
                                "contract": "SN.SHF",
                                "open_interest": 3000 + idx,
                                "settlement": 210020 + idx,
                            }
                            for idx, day in enumerate(days)
                        ],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            (diagnostics / "real_data_coverage_validation.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-01-01T00:00:00",
                        "feature_coverage_before": _coverage({"raw_market": 0.833333, "inventory": 0.0, "term_structure": 0.166667}),
                        "feature_coverage_after": _coverage({"raw_market": 0.833333, "inventory": 0.0, "term_structure": 0.166667}),
                        "feature_store_v5": {"status": "success", "usable_fields": [], "tushare_used": False, "no_lookahead_pass": True, "leakage_check_pass": True},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )

            feature_store = build_feature_store_v5()
            readiness = get_candidate_v6_readiness()

        self.assertTrue(feature_store["tushare_used"])
        self.assertEqual(readiness["status"], "ready")
        self.assertIn("raw_market", readiness["new_factor_groups"])
        self.assertIn("open_interest", readiness["new_fields"])


if __name__ == "__main__":
    unittest.main()
