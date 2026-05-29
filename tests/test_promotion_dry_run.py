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

from sn_futures.services.model_promotion_service import promote_candidate
from sn_futures.services.training_dataset_service import build_training_dataset
from sn_futures.services.walk_forward_training_service import run_candidate_training


def _write_history(root: str, rows: int = 240) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2024-01-01", periods=rows, freq="D")):
        close = 250000.0 + idx * 42.0 + (idx % 19) * 90.0
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 170,
                "high": close + 470,
                "low": close - 460,
                "close": close,
                "volume": 9900 + idx,
                "open_interest": 170000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class PromotionDryRunTest(unittest.TestCase):
    def test_v2_promotion_dry_run_never_writes_active_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            build_training_dataset(horizons=(1,), dataset_version="v2", feature_set="ohlcv_technical_regime_cross_market_event")
            run_candidate_training(horizons=("1d",), candidate_version="v2", dataset_version="v2")

            report = promote_candidate(candidate_version="v2", dry_run=True)

            self.assertEqual(report["candidate_version"], "v2")
            self.assertTrue(report["dry_run"])
            self.assertFalse(report["active_updated"])
            self.assertFalse(report["customer_prediction_generated"])
            self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())


if __name__ == "__main__":
    unittest.main()
