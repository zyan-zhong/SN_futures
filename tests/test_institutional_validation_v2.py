from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.institutional_validation_service import run_institutional_validation
from sn_futures.services.training_dataset_service import build_training_dataset
from sn_futures.services.walk_forward_training_service import run_candidate_training


def _write_history(root: str, rows: int = 240) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2024-01-01", periods=rows, freq="D")):
        close = 240000.0 + idx * 40.0 + (idx % 17) * 85.0
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 150,
                "high": close + 450,
                "low": close - 430,
                "close": close,
                "volume": 9800 + idx,
                "open_interest": 160000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class InstitutionalValidationV2Test(unittest.TestCase):
    def test_institutional_validation_v2_is_dry_run_and_does_not_write_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            build_training_dataset(horizons=(1,), dataset_version="v2", feature_set="ohlcv_technical_regime_cross_market_event")
            run_candidate_training(horizons=("1d",), candidate_version="v2", dataset_version="v2")

            report = run_institutional_validation(candidate_version="v2", dry_run=True)

            self.assertEqual(report["candidate_version"], "v2")
            self.assertTrue(report["dry_run"])
            self.assertFalse(report["active_updated"])
            self.assertFalse(report["promotion_gate_lowered"])
            self.assertFalse(report["customer_prediction_generated"])
            self.assertIn("deflated_sharpe_ratio", report)
            self.assertIn("probability_of_backtest_overfitting", report)
            self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()
