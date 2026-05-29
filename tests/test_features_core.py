from __future__ import annotations

import sys
import unittest
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.features_core import build_feature_matrix, build_technical_factors


def sample_ohlcv(rows: int = 90) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=rows, freq="B")
    t = np.arange(rows, dtype=float)
    close = 420000 + 2200 * np.sin(t / 8.0) + t * 45
    return pd.DataFrame(
        {
            "open": close + 120 * np.sin(t / 3.0),
            "high": close + 900,
            "low": close - 900,
            "close": close,
            "volume": 10000 + 500 * np.cos(t / 5.0),
            "open_interest": 52000 + 200 * np.sin(t / 7.0),
            "main_contract": "sn2606",
        },
        index=idx,
    )


class FeaturesCoreTests(unittest.TestCase):
    def test_technical_factors_from_small_ohlcv(self) -> None:
        factors, metadata, missing = build_technical_factors(sample_ohlcv())
        self.assertIn("ema_spread_5_20", factors.columns)
        self.assertIn("rsi_14", factors.columns)
        self.assertIn("obv_slope_10", factors.columns)
        self.assertGreater(len(metadata), 10)
        self.assertEqual(missing, {})

    def test_missing_optional_data_reports_chinese_reason(self) -> None:
        result = build_feature_matrix(sample_ohlcv())
        self.assertIn("lme_inventory", result.missing_feature_report)
        self.assertIn("数据暂缺", result.missing_feature_report["lme_inventory"])
        self.assertIn("spot_price", result.missing_feature_report)
        self.assertGreater(result.data_quality_score, 0.0)

    def test_feature_matrix_excludes_label_columns(self) -> None:
        frame = sample_ohlcv()
        frame["ret_1d"] = 0.01
        frame["direction_1d"] = 1
        frame["tb_label"] = 1
        frame["meta_target"] = 1
        result = build_feature_matrix(frame)
        for column in ("ret_1d", "direction_1d", "tb_label", "meta_target"):
            self.assertNotIn(column, result.feature_df.columns)

    def test_regime_label_and_metadata_exist(self) -> None:
        result = build_feature_matrix(sample_ohlcv())
        self.assertIn("regime_label", result.feature_df.columns)
        self.assertTrue(set(result.feature_df["regime_label"].dropna()).issubset({
            "TREND_UP_LOW_VOL",
            "TREND_UP_HIGH_VOL",
            "TREND_DOWN_LOW_VOL",
            "TREND_DOWN_HIGH_VOL",
            "RANGE_LOW_VOL",
            "RANGE_HIGH_VOL",
            "EVENT_SHOCK",
            "DELIVERY_SQUEEZE",
            "LIQUIDITY_THIN",
        }))
        self.assertGreater(len(result.feature_metadata), 30)
        self.assertIn("technical", result.factor_groups)


if __name__ == "__main__":
    unittest.main()
