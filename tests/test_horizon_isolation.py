from __future__ import annotations

import sys
import unittest

sys.path.insert(0, "src")

from sn_futures.chart_alignment import build_forecast_curve, validate_chart_alignment
from sn_futures.horizon_registry import HORIZON_ORDER, get_horizon_config
from sn_futures.model_registry import load_registry


class HorizonIsolationTest(unittest.TestCase):
    def test_registry_keys_are_unique_per_horizon(self) -> None:
        rows = load_registry()
        self.assertEqual(len(rows), 7)
        for field in ("artifact_path", "scaler_id", "forecast_index_hash", "prediction_cache_key"):
            values = [row[field] for row in rows]
            self.assertEqual(len(values), len(set(values)), field)

    def test_future_indexes_are_distinct_and_after_history(self) -> None:
        history = [{"date": "2026-05-14T15:00:00+08:00", "close": 420000}]
        hashes = set()
        lengths = {}
        for key in HORIZON_ORDER:
            cfg = get_horizon_config(key)
            card = {
                "anchor_close": 420000,
                "price_center": 421000 + cfg.forecast_steps,
                "range_low": 419000,
                "range_high": 423000,
                "prob_up": 0.53 + cfg.forecast_steps / 1000,
            }
            forecast = build_forecast_curve(live_card=card, last_timestamp=history[-1]["date"], horizon_key=key)
            self.assertEqual(len(forecast), cfg.forecast_steps)
            self.assertTrue(validate_chart_alignment(history, forecast)["ok"])
            index_hash = tuple(row["date"] for row in forecast)
            self.assertNotIn(index_hash, hashes)
            hashes.add(index_hash)
            lengths[key] = len(forecast)
        self.assertNotEqual(lengths["next_5m"], lengths["next_15m"])
        self.assertNotEqual(lengths["next_hour"], lengths["tomorrow"])

    def test_prediction_arrays_are_not_identical(self) -> None:
        curves = []
        for key in HORIZON_ORDER:
            cfg = get_horizon_config(key)
            forecast = build_forecast_curve(
                live_card={
                    "anchor_close": 420000,
                    "price_center": 420000 + cfg.forecast_steps * 10,
                    "range_low": 419000,
                    "range_high": 421500 + cfg.forecast_steps * 10,
                    "prob_up": 0.50 + cfg.forecast_steps / 1000,
                },
                last_timestamp="2026-05-14T15:00:00+08:00",
                horizon_key=key,
            )
            curves.append(tuple((row["date"], round(row["pred_center"], 4), row["prob_up"]) for row in forecast))
        self.assertEqual(len(curves), len(set(curves)))


if __name__ == "__main__":
    unittest.main()
