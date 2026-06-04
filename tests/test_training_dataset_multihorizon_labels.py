from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from sn_futures.services.feature_store_service import build_feature_store
from sn_futures.services.training_dataset_service import build_training_dataset


def _write_market_history(root: Path, *, periods: int = 100) -> None:
    output = root / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    for idx, day in enumerate(pd.date_range("2026-01-01", periods=periods, freq="D")):
        close = 200_000.0 + idx * 100.0
        rows.append(
            {
                "trade_date": day.strftime("%Y-%m-%d"),
                "open": close - 50,
                "high": close + 200,
                "low": close - 200,
                "close": close,
                "volume": 1_000 + idx,
                "open_interest": 5_000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(
        json.dumps({"history": rows, "sample": False}, ensure_ascii=False),
        encoding="utf-8",
    )


def _build_v3_dataset(root: Path, horizons: tuple[str, ...]) -> dict[str, object]:
    with patch.dict(os.environ, {"SN_DATA_DIR": str(root)}, clear=False):
        build_feature_store(version="v3")
        return build_training_dataset(
            dataset_version="v3",
            feature_store_version="v3",
            feature_set="ohlcv_technical_regime_cross_market_event",
            horizons=horizons,
        )


def _read_dataset(path: str) -> pd.DataFrame:
    dataset_path = Path(path)
    if dataset_path.suffix == ".parquet":
        return pd.read_parquet(dataset_path)
    return pd.read_csv(dataset_path)


def test_named_horizon_label_specs_and_tail_exclusion_are_manifested(tmp_path: Path) -> None:
    _write_market_history(tmp_path, periods=100)

    manifest = _build_v3_dataset(tmp_path, ("tomorrow", "one_to_two_weeks"))

    assert manifest["status"] == "success"
    assert manifest["label_version"] == "label_v1_multi_horizon_pit"
    assert manifest["label_specs"]["tomorrow"]["required_future_bars"] == 1
    assert manifest["label_specs"]["one_to_two_weeks"]["required_future_bars"] == 10
    assert manifest["sample_count_by_horizon"]["tomorrow"] == 99
    assert manifest["sample_count_by_horizon"]["one_to_two_weeks"] == 90

    tomorrow = _read_dataset(manifest["dataset_paths"]["tomorrow"])
    two_weeks = _read_dataset(manifest["dataset_paths"]["one_to_two_weeks"])
    assert tomorrow["horizon"].unique().tolist() == ["tomorrow"]
    assert two_weeks["horizon"].unique().tolist() == ["one_to_two_weeks"]
    assert pd.Timestamp(tomorrow["label_start_time"].max()) == pd.Timestamp("2026-04-09")
    assert pd.Timestamp(two_weeks["label_start_time"].max()) == pd.Timestamp("2026-03-31")
    assert set(["target_return", "direction_label", "volatility_adjusted_label", "label_available_at"]).issubset(tomorrow.columns)


def test_feature_time_and_label_fields_are_not_usable_features(tmp_path: Path) -> None:
    _write_market_history(tmp_path, periods=90)

    manifest = _build_v3_dataset(tmp_path, ("tomorrow",))

    forbidden = {"feature_time", "label_available_at", "label_end_time", "target_return", "direction_label"}
    assert forbidden.isdisjoint(set(manifest["feature_cols"]))
    dataset = _read_dataset(manifest["dataset_paths"]["tomorrow"])
    assert (pd.to_datetime(dataset["feature_time"]) < pd.to_datetime(dataset["label_available_at"])).all()
    assert dataset["horizon"].unique().tolist() == ["tomorrow"]


def test_intraday_horizon_blocks_when_feature_store_contains_daily_bars(tmp_path: Path) -> None:
    _write_market_history(tmp_path, periods=90)

    manifest = _build_v3_dataset(tmp_path, ("next_15m",))

    assert manifest["status"] == "blocked"
    assert manifest["dataset_paths"] == {}
    assert "next_15m:intraday_horizon_requires_intraday_bars" in manifest["blocked_reasons"]
    assert manifest["horizon_manifests"]["next_15m"]["bar_interval_seconds_median"] >= 86_400


def test_insufficient_future_samples_blocks_dataset_without_writing_training_data(tmp_path: Path) -> None:
    _write_market_history(tmp_path, periods=70)

    manifest = _build_v3_dataset(tmp_path, ("one_to_three_months",))

    assert manifest["status"] == "blocked"
    assert manifest["sample_count_by_horizon"]["one_to_three_months"] == 10
    assert manifest["dataset_paths"] == {}
    assert any(reason.startswith("one_to_three_months:insufficient_samples") for reason in manifest["blocked_reasons"])
    dataset_dir = tmp_path / "outputs" / "training_datasets" / "v3"
    assert not any(dataset_dir.glob("train_one_to_three_months.*")) if dataset_dir.exists() else True
