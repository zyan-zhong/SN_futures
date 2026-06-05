from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.services.prediction_layers_service import (
    build_no_active_model_prediction_payload,
    build_terminal_display_card,
    is_terminal_display_card_allowed_as_input,
)
from sn_futures.unified_forecast import build_unified_forecast
from sn_futures.v2_api import get_live_predictions


def test_display_card_is_forbidden_for_feature_store_training_and_backtest() -> None:
    card = build_terminal_display_card(
        horizon="tomorrow",
        guarded_signal={
            "allowed_for_customer_display": True,
            "signal": "neutral",
            "abstain": True,
            "abstain_reasons": ["direction_edge_too_weak"],
        },
        source_card={"direction_label": "neutral", "risk_notes": ["research only"]},
    )

    assert card["layer"] == "TerminalDisplayCard"
    assert card["allowed_for_feature_store"] is False
    assert card["allowed_for_training"] is False
    assert card["allowed_for_backtest"] is False
    assert is_terminal_display_card_allowed_as_input(card, purpose="feature_store") is False
    assert is_terminal_display_card_allowed_as_input(card, purpose="training") is False
    assert is_terminal_display_card_allowed_as_input(card, purpose="backtest") is False


def test_unified_forecast_exposes_raw_calibrated_guarded_and_display_layers(tmp_path: Path) -> None:
    payload = build_unified_forecast(
        {
            "cards": {
                "tomorrow": {
                    "model_id": "active-sn-direction-v1",
                    "horizon": "tomorrow",
                    "prob_up": 0.62,
                    "prob_down": 0.28,
                    "prob_neutral": 0.10,
                    "expected_return": 0.012,
                    "price_center": 101.2,
                    "range_low": 98.0,
                    "range_high": 104.0,
                    "confidence_score": 0.71,
                    "feature_manifest_hash": "feature-manifest-sha",
                }
            }
        },
        output_dir=tmp_path,
        data_watermark={
            "quality_score": 0.82,
            "latest_daily": "2026-01-06",
            "source_mode": "remote",
            "sample_data_used": False,
            "baseline_used": False,
        },
        persist=False,
    )

    card = payload["cards"]["tomorrow"]
    assert payload["prediction_layers_schema_version"] == 1
    assert card["raw_layer"]["layer"] == "RawModelPrediction"
    assert card["raw_layer"]["model_id"] == "active-sn-direction-v1"
    assert card["raw_layer"]["raw_prob_up"] == 0.62
    assert card["raw_layer"]["raw_expected_return"] == 0.012
    assert card["raw_layer"]["feature_manifest_hash"] == "feature-manifest-sha"
    assert card["calibrated_layer"]["layer"] == "CalibratedPrediction"
    assert card["calibrated_layer"]["calibration_status"] == "uncalibrated"
    assert card["calibrated_layer"]["calibration_model_id"] == ""
    assert card["calibrated_layer"]["brier"] is None
    assert card["calibrated_layer"]["ece"] is None
    assert card["guarded_layer"]["layer"] == "GuardedResearchSignal"
    assert card["guarded_layer"]["data_gate"]["allowed"] is True
    assert card["display_layer"]["layer"] == "TerminalDisplayCard"
    assert card["display_layer"]["allowed_for_backtest"] is False


def test_data_gate_failure_returns_blocked_display_only_payload(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))

    payload = get_live_predictions()

    assert payload["status"] == "blocked"
    assert payload["cards"] == {}
    assert payload["raw_layer"] is None
    assert payload["calibrated_layer"] is None
    assert payload["guarded_layer"]["layer"] == "GuardedResearchSignal"
    assert payload["guarded_layer"]["abstain"] is True
    assert payload["guarded_layer"]["allowed_for_prediction"] is False
    assert payload["display_layer"]["layer"] == "TerminalDisplayCard"
    assert payload["display_layer"]["display_only"] is True
    assert payload["display_layer"]["allowed_for_backtest"] is False


def test_no_active_model_returns_no_fake_prediction_layers() -> None:
    payload = build_no_active_model_prediction_payload(data_watermark={"latest_daily": "2026-01-06"})

    assert payload["status"] == "blocked"
    assert payload["cards"] == {}
    assert payload["raw_layer"] is None
    assert payload["calibrated_layer"] is None
    assert "no_active_model" in payload["blocking_reasons"]
    assert payload["guarded_layer"]["allowed_for_prediction"] is False
    assert payload["display_layer"]["layer"] == "TerminalDisplayCard"
    assert payload["display_layer"]["display_only"] is True
