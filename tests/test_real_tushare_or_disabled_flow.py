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

from sn_futures.services.real_data_coverage_validation_service import build_real_data_coverage_validation


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_market_history(output_dir: Path, rows: int = 140) -> None:
    start = date(2026, 1, 1)
    history = []
    for idx in range(rows):
        day = (start + timedelta(days=idx)).isoformat()
        close = 250000 + idx * 5
        history.append({"trade_date": day, "open": close - 30, "high": close + 80, "low": close - 90, "close": close, "volume": 1000 + idx})
    _write_json(output_dir / "sn_market_history.json", {"sample": False, "history": history})


class RealTushareOrDisabledFlowTest(unittest.TestCase):
    def test_token_missing_blocks_v6_readiness_and_does_not_train(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_TUSHARE_TOKEN": "",
                "SN_MANAGED_DATA_PROXY_TOKEN": "",
                "SN_MANAGED_DATA_PROXY_URL": "",
                "SN_MANAGED_DATA_PROXY_ENABLED": "",
            },
            clear=False,
        ):
            output_dir = Path(tmp) / "outputs"
            _write_market_history(output_dir)

            report = build_real_data_coverage_validation(force=False)

            self.assertEqual(report["source_status"]["tushare"]["status"], "token_missing")
            self.assertEqual(report["candidate_v6_readiness"]["status"], "blocked")
            self.assertIn("new_real_factor_group_missing", report["candidate_v6_readiness"]["blocked_reasons"])
            self.assertFalse(report["training_invoked"])
            self.assertFalse(report["active_updated"])
            self.assertFalse(report["customer_prediction_generated"])
            self.assertTrue((output_dir / "diagnostics" / "real_data_coverage_validation.json").exists())
            self.assertTrue((output_dir / "diagnostics" / "real_data_coverage_validation.md").exists())
            self.assertFalse((output_dir / "model_registry" / "active_model.json").exists())
            self.assertFalse((output_dir / "sn_live_predictions.json").exists())
            self.assertFalse((output_dir / "customer_predictions.json").exists())


if __name__ == "__main__":
    unittest.main()
