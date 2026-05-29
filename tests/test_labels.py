import sys
import unittest
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.labels import (
    add_forward_return_labels,
    add_meta_labels,
    add_triple_barrier_labels,
    check_feature_label_leakage,
    check_label_timestamps,
    check_train_test_label_window_overlap,
    forward_label_columns,
)


class LabelTests(unittest.TestCase):
    def test_forward_return_labels_are_shifted_future_returns(self) -> None:
        frame = pd.DataFrame(
            {
                "close": [100.0, 110.0, 121.0, 115.0, 120.0, 130.0],
                "high": [101.0, 112.0, 123.0, 118.0, 124.0, 132.0],
                "low": [99.0, 108.0, 119.0, 113.0, 117.0, 128.0],
            },
            index=pd.date_range("2026-01-01", periods=6, freq="D"),
        )
        labeled = add_forward_return_labels(frame, horizons=(1, 3), direction_threshold=0.0)
        self.assertAlmostEqual(float(labeled.loc[labeled.index[0], "ret_1d"]), 0.10)
        self.assertAlmostEqual(float(labeled.loc[labeled.index[0], "ret_3d"]), 0.15)
        self.assertEqual(int(labeled.loc[labeled.index[0], "direction_1d"]), 1)
        self.assertAlmostEqual(float(labeled.loc[labeled.index[0], "max_favorable_excursion_3d"]), 0.23)
        self.assertAlmostEqual(float(labeled.loc[labeled.index[0], "max_adverse_excursion_3d"]), 0.08)
        self.assertTrue(pd.isna(labeled.loc[labeled.index[-1], "ret_1d"]))

    def test_triple_barrier_hits_upper_and_lower(self) -> None:
        frame = pd.DataFrame(
            {
                "close": [100.0, 101.0, 102.0, 101.0],
                "high": [100.5, 112.0, 103.0, 102.0],
                "low": [99.5, 100.0, 88.0, 100.0],
                "atr_14": [10.0, 10.0, 10.0, 10.0],
            },
            index=pd.date_range("2026-01-01", periods=4, freq="D"),
        )
        labeled = add_triple_barrier_labels(frame, horizon=2, k_up=1.0, k_down=1.0, side="long")
        self.assertEqual(int(labeled.loc[labeled.index[0], "tb_label"]), 1)
        self.assertEqual(labeled.loc[labeled.index[0], "tb_hit_time"], labeled.index[1])

        short_labeled = add_triple_barrier_labels(frame, horizon=2, k_up=1.0, k_down=1.0, side="short")
        self.assertEqual(int(short_labeled.loc[short_labeled.index[1], "tb_label"]), 1)

    def test_triple_barrier_conservative_same_bar_double_hit(self) -> None:
        frame = pd.DataFrame(
            {
                "close": [100.0, 100.0, 100.0],
                "high": [100.0, 112.0, 100.0],
                "low": [100.0, 88.0, 100.0],
                "atr_14": [10.0, 10.0, 10.0],
            },
            index=pd.date_range("2026-01-01", periods=3, freq="D"),
        )
        long_labeled = add_triple_barrier_labels(frame, horizon=1, side="long", conservative=True)
        short_labeled = add_triple_barrier_labels(frame, horizon=1, side="short", conservative=True)
        self.assertEqual(int(long_labeled.loc[long_labeled.index[0], "tb_label"]), -1)
        self.assertEqual(int(short_labeled.loc[short_labeled.index[0], "tb_label"]), -1)

    def test_triple_barrier_close_only_fallback(self) -> None:
        frame = pd.DataFrame(
            {"close": [100.0, 111.0, 90.0], "atr_14": [10.0, 10.0, 10.0]},
            index=pd.date_range("2026-01-01", periods=3, freq="D"),
        )
        labeled = add_triple_barrier_labels(frame, horizon=1, side="long")
        self.assertEqual(int(labeled.loc[labeled.index[0], "tb_label"]), 1)

    def test_meta_labeling_excludes_no_trade(self) -> None:
        frame = pd.DataFrame(
            {
                "primary_signal": ["long_candidate", "short_candidate", "no_trade", "long_candidate"],
                "tb_label": [1, 1, 1, -1],
            }
        )
        labeled = add_meta_labels(frame, side_adjusted_tb=True)
        self.assertEqual(int(labeled.loc[0, "meta_target"]), 1)
        self.assertEqual(int(labeled.loc[1, "meta_target"]), 1)
        self.assertTrue(pd.isna(labeled.loc[2, "meta_target"]))
        self.assertEqual(int(labeled.loc[3, "meta_target"]), 0)

    def test_label_columns_do_not_enter_features(self) -> None:
        labels = forward_label_columns((1, 3))
        clean = check_feature_label_leakage(["close", "volume"], labels)
        dirty = check_feature_label_leakage(["close", "ret_1d"], labels)
        self.assertTrue(clean["ok"])
        self.assertFalse(dirty["ok"])
        self.assertIn("ret_1d", dirty["leaked_columns"])

    def test_timestamp_and_window_leakage_guards(self) -> None:
        time_check = check_label_timestamps(
            ["2026-01-01", "2026-01-02"],
            ["2026-01-02", "2026-01-03"],
        )
        self.assertTrue(time_check["ok"])
        overlap = check_train_test_label_window_overlap(
            train_end="2026-01-10",
            test_start="2026-01-12",
            max_horizon_days=5,
        )
        self.assertFalse(overlap["ok"])


if __name__ == "__main__":
    unittest.main()

