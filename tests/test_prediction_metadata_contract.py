import unittest

from sn_futures.v2_api import _ensure_prediction_metadata


class PredictionMetadataContractTest(unittest.TestCase):
    def test_live_cards_receive_required_release_blocker_metadata(self) -> None:
        payload = {
            "cards": {
                "h5m": {
                    "horizon": "h5m",
                    "price_center": 421000.0,
                    "p_up": 0.57,
                    "p_down": 0.31,
                    "p_neutral": 0.12,
                    "confidence_score": 0.64,
                }
            },
            "live_quote": {
                "latest_price": 421000.0,
                "source_timestamp": "2026-05-15T22:15:00+08:00",
                "fetch_timestamp": "2026-05-15T22:15:05+08:00",
                "source": "sina",
            },
        }
        watermark = {
            "latest_price": 421000.0,
            "latest_quote_time": "2026-05-15T22:15:00+08:00",
            "fetch_timestamp": "2026-05-15T22:15:05+08:00",
            "source": "sina",
            "data_age_seconds": 5.0,
        }

        _ensure_prediction_metadata(payload, watermark)
        card = payload["cards"]["h5m"]

        required = [
            "prediction_id",
            "model_version",
            "direction_model_version",
            "price_model_version",
            "calibrator_version",
            "data_timestamp",
            "source_timestamp",
            "fetch_timestamp",
            "feature_set_id",
            "dataset_id",
            "label_config_id",
            "scaler_id",
            "prediction_cache_key",
            "event_feature_hash",
            "active_or_candidate_status",
            "promotion_result",
            "signal_strength",
        ]
        missing = [name for name in required if not card.get(name)]
        self.assertEqual([], missing)
        self.assertIn("h5m", card["prediction_cache_key"])
        self.assertIn(card["signal_strength"], {"strong_up", "weak_up", "neutral", "weak_down", "strong_down", "abstain"})


if __name__ == "__main__":
    unittest.main()
