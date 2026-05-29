import sys
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.models.baselines import train_baseline_models
from sn_futures.models.calibration import fit_probability_calibrator
from sn_futures.models.ensemble import selective_signal
from sn_futures.models.predict import predict_horizon
from sn_futures.models.train import train_horizon_models
from sn_futures.models.tree_models import train_tree_model_bundle


def sample_frame(rows: int = 80) -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=rows, freq="D")
    t = np.arange(rows, dtype=float)
    f1 = np.sin(t / 4.0)
    f2 = np.cos(t / 7.0)
    ret = 0.006 * np.sign(f1 + 0.25 * f2)
    ret += 0.001 * np.sin(t / 3.0)
    direction = np.where(ret > 0, 1, -1)
    close = 420000 * (1 + pd.Series(ret, index=idx).fillna(0).cumsum() * 0.02)
    return pd.DataFrame(
        {
            "f1": f1,
            "f2": f2,
            "ret_1d": ret,
            "direction_1d": direction,
            "regime_label": np.where(t % 3 == 0, "trend", "range"),
            "close": close.to_numpy(dtype=float),
            "realized_vol_5d": 0.012 + 0.001 * np.abs(f2),
        },
        index=idx,
    )


class ModelFrameworkTests(unittest.TestCase):
    def test_small_sample_can_train_baseline(self) -> None:
        frame = sample_frame(18)
        bundle = train_baseline_models(
            frame,
            ["f1", "f2"],
            horizon="h1d",
            direction_col="direction_1d",
            return_col="ret_1d",
        )
        self.assertEqual(bundle.horizon, "h1d")
        self.assertIn("directional_accuracy", bundle.metrics)

    def test_tree_model_falls_back_when_lightgbm_missing(self) -> None:
        frame = sample_frame(50)
        with patch("sn_futures.models.tree_models.importlib.import_module", side_effect=ImportError()):
            bundle = train_tree_model_bundle(
                frame.iloc[:35],
                frame.iloc[35:],
                ["f1", "f2"],
                horizon="h1d",
                direction_col="direction_1d",
                return_col="ret_1d",
                feature_set_version="test_features",
            )
        self.assertEqual(bundle.backend, "sklearn_hist_gradient")
        self.assertEqual(bundle.horizon, "h1d")

    def test_calibrated_probability_is_bounded(self) -> None:
        raw = [0.10, 0.25, 0.40, 0.55, 0.70, 0.90] * 3
        y = [0, 0, 0, 1, 1, 1] * 3
        calibrator = fit_probability_calibrator(raw, y, method="sigmoid")
        values = calibrator.transform([0.01, 0.5, 0.99])
        self.assertTrue(np.all(values >= 0.0))
        self.assertTrue(np.all(values <= 1.0))

    def test_edge_not_positive_outputs_observation(self) -> None:
        result = selective_signal(
            calibrated_prob_up=0.70,
            trade_edge=-0.001,
            data_quality_score=0.90,
            model_health="ok",
        )
        self.assertEqual(result["signal"], "观望")

    def test_bad_data_quality_outputs_observation_in_contract(self) -> None:
        frame = sample_frame(70)
        bundle = train_horizon_models(
            frame,
            ["f1", "f2"],
            horizon="h1d",
            direction_col="direction_1d",
            return_col="ret_1d",
            validation_fraction=0.25,
        )
        payload = predict_horizon(bundle, frame.iloc[-1], data_quality_score=0.20, current_price=420000.0)
        self.assertEqual(payload["signal"], "观望")
        self.assertIn("horizon", payload)
        self.assertIn("raw_prob_up", payload)
        self.assertIn("calibrated_prob_up", payload)
        self.assertGreaterEqual(payload["calibrated_prob_up"], 0.0)
        self.assertLessEqual(payload["calibrated_prob_up"], 1.0)


if __name__ == "__main__":
    unittest.main()

