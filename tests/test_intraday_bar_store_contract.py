from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.labels.horizons import build_intraday_label_gate  # noqa: E402
from sn_futures.services.intraday_bar_store_service import (  # noqa: E402
    build_latest_quote_tick_manifest,
    get_intraday_bar_store_status,
    write_intraday_bars,
)
from sn_futures.services.training_dataset_service import build_training_dataset  # noqa: E402


def test_latest_quote_manifest_is_display_tick_not_intraday_bar() -> None:
    manifest = build_latest_quote_tick_manifest(
        {
            "symbol": "SN",
            "exchange": "SHFE",
            "latest": 208_000.0,
            "quote_time": "2026-06-07T10:15:00+08:00",
            "provider": "sina",
        }
    )

    assert manifest["data_kind"] == "latest_quote_tick"
    assert manifest["display_only"] is True
    assert manifest["immutable_intraday_bar"] is False
    assert manifest["allowed_for_feature_store"] is False
    assert manifest["allowed_for_training"] is False
    assert manifest["allowed_for_prediction"] is False
    assert manifest["allowed_for_backtest"] is False
    assert manifest["allowed_for_intraday_label"] is False
    assert manifest["latest_quote_used_as_intraday_bar"] is False


def test_intraday_bar_store_rejects_daily_rows_as_minute_bars(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))

    result = write_intraday_bars(
        [
            {
                "bar_start": "2026-06-01",
                "bar_end": "2026-06-02",
                "open": 200_000,
                "high": 202_000,
                "low": 199_000,
                "close": 201_000,
                "volume": 10,
            }
        ],
        symbol="SN",
        interval="5m",
        provider="contract_test",
        fetched_at="2026-06-07T10:30:00+08:00",
    )

    assert result["status"] == "blocked"
    assert result["row_count"] == 0
    assert result["daily_bar_used_as_intraday"] is True
    assert "daily_bar_used_as_intraday" in result["blocking_reasons"]
    assert result["latest_quote_used"] is False
    assert result["bars_path"] == ""
    assert Path(result["manifest_path"]).exists()


def test_intraday_bar_store_writes_immutable_bars_and_manifest(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))

    result = write_intraday_bars(
        [
            {
                "bar_start": "2026-06-01T09:00:00+08:00",
                "bar_end": "2026-06-01T09:05:00+08:00",
                "open": 200_000,
                "high": 201_000,
                "low": 199_500,
                "close": 200_500,
                "volume": 10,
                "open_interest": 100,
            },
            {
                "bar_start": "2026-06-01T09:05:00+08:00",
                "bar_end": "2026-06-01T09:10:00+08:00",
                "open": 200_500,
                "high": 201_500,
                "low": 200_000,
                "close": 201_000,
                "volume": 12,
                "open_interest": 102,
            },
        ],
        symbol="SN",
        interval="5m",
        active_contract="sn2606",
        provider="contract_test",
        source_url_sanitized="https://example.invalid/intraday",
        fetched_at="2026-06-07T10:30:00+08:00",
        as_of="2026-06-01T09:10:00+08:00",
    )

    assert result["status"] == "success"
    assert result["data_kind"] == "intraday_bar"
    assert result["row_count"] == 2
    assert result["history_immutable"] is True
    assert result["latest_quote_used"] is False
    assert result["daily_bar_used_as_intraday"] is False
    assert result["sample_data_used"] is False
    assert result["baseline_used"] is False
    assert result["allowed_for_training"] is True
    assert result["allowed_for_prediction"] is True
    assert result["content_hash"]
    assert Path(result["bars_path"]).exists()
    assert Path(result["manifest_path"]).exists()

    with Path(result["bars_path"]).open("r", encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["interval"] == "5m"
    assert rows[0]["active_contract"] == "sn2606"

    status = get_intraday_bar_store_status(symbol="SN", interval="5m")
    assert status["status"] == "success"
    assert status["row_count"] == 2
    assert status["allowed_for_intraday_label"] is True


def test_short_horizon_label_gate_blocks_without_real_intraday_bars(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))

    gate = build_intraday_label_gate(["next_5m", "next_15m", "next_30m", "next_hour", "tomorrow"])

    for horizon in ("next_5m", "next_15m", "next_30m", "next_hour"):
        row = gate["horizons"][horizon]
        assert row["allowed"] is False
        assert "intraday_bars_missing" in row["blocking_reasons"]
        assert "latest_quote_is_display_tick_not_label_source" in row["blocking_reasons"]
        assert row["daily_bar_used_as_intraday"] is False
    assert gate["horizons"]["tomorrow"]["allowed"] is True


def test_short_horizon_label_gate_allows_only_matching_intraday_interval(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    write_intraday_bars(
        [
            {
                "bar_start": "2026-06-01T09:00:00+08:00",
                "bar_end": "2026-06-01T09:05:00+08:00",
                "open": 200_000,
                "high": 201_000,
                "low": 199_500,
                "close": 200_500,
                "volume": 10,
            }
        ],
        symbol="SN",
        interval="5m",
        provider="contract_test",
        fetched_at="2026-06-07T10:30:00+08:00",
    )

    gate = build_intraday_label_gate(["next_5m", "next_15m"])

    assert gate["horizons"]["next_5m"]["allowed"] is True
    assert gate["horizons"]["next_5m"]["store_manifest"]["interval"] == "5m"
    assert gate["horizons"]["next_15m"]["allowed"] is False
    assert "intraday_bars_missing" in gate["horizons"]["next_15m"]["blocking_reasons"]


def test_training_dataset_blocks_short_horizon_when_only_daily_feature_store_exists(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path / "user_data"))
    feature_dir = tmp_path / "user_data" / "outputs" / "feature_store" / "v3"
    feature_dir.mkdir(parents=True, exist_ok=True)
    frame = pd.DataFrame(
        [
            {
                "trade_date": day.strftime("%Y-%m-%d"),
                "open": 200_000 + idx,
                "high": 201_000 + idx,
                "low": 199_000 + idx,
                "close": 200_500 + idx,
                "volume": 1000 + idx,
            }
            for idx, day in enumerate(pd.date_range("2026-01-01", periods=80, freq="D"))
        ]
    )
    store_path = feature_dir / "feature_store.csv"
    frame.to_csv(store_path, index=False, encoding="utf-8")
    manifest_path = feature_dir / "feature_store_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "version": "v3",
                "feature_store_path": str(store_path),
                "manifest_path": str(manifest_path),
                "usable_fields": ["open", "high", "low", "close", "volume"],
                "sample_data_used": False,
                "baseline_used": False,
                "leakage_check_pass": True,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    manifest = build_training_dataset(horizons=("next_5m",), dataset_version="v3", feature_store_version="v3")

    assert manifest["status"] == "blocked"
    assert manifest["dataset_paths"] == {}
    assert "next_5m:intraday_bars_missing" in manifest["blocked_reasons"]
    assert "next_5m:latest_quote_is_display_tick_not_label_source" in manifest["blocked_reasons"]
    assert "next_5m:intraday_horizon_requires_intraday_bars" in manifest["blocked_reasons"]
    horizon_manifest = manifest["horizon_manifests"]["next_5m"]
    assert horizon_manifest["intraday_label_gate"]["allowed"] is False
    assert horizon_manifest["intraday_label_gate"]["store_manifest"]["row_count"] == 0
