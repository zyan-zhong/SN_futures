from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from sn_futures.services.feature_store_service import build_feature_store


def _write_market_history(root: Path, *, start: str = "2026-01-01", periods: int = 80) -> list[dict[str, object]]:
    outputs = root / "outputs"
    outputs.mkdir(parents=True, exist_ok=True)
    dates = pd.date_range(start=start, periods=periods, freq="D")
    rows: list[dict[str, object]] = []
    for idx, day in enumerate(dates):
        close = 200_000 + idx
        rows.append(
            {
                "trade_date": day.strftime("%Y-%m-%d"),
                "open": close - 20,
                "high": close + 30,
                "low": close - 40,
                "close": close,
                "volume": 1_000 + idx,
                "open_interest": 5_000 + idx,
                "ret_1d": 0.99,
                "direction_1d": 1,
                "display_overlay": {"type": "latest_quote_marker", "latest": close + 100},
                "live_quote": {"latest": close + 100},
            }
        )
    (outputs / "sn_market_history.json").write_text(
        json.dumps({"rows": rows, "source_path": str(outputs / "sn_market_history.json")}, ensure_ascii=False),
        encoding="utf-8",
    )
    return rows


def _read_feature_frame(result: dict[str, object]) -> pd.DataFrame:
    return pd.read_csv(str(result["feature_store_path"]))


def _build_with_data_dir(root: Path) -> dict[str, object]:
    with patch.dict(os.environ, {"SN_DATA_DIR": str(root)}, clear=False):
        return build_feature_store(version="v3")


def test_feature_store_manifest_excludes_forward_return_and_label_columns(tmp_path: Path) -> None:
    _write_market_history(tmp_path)

    result = _build_with_data_dir(tmp_path)

    assert result["status"] == "success"
    manifest = result
    frame = _read_feature_frame(result)
    usable_fields = set(manifest["usable_fields"])
    assert "ret_1d" not in usable_fields
    assert "direction_1d" not in usable_fields
    assert "ret_1d" not in frame.columns
    assert "direction_1d" not in frame.columns
    assert manifest["leakage_check_pass"] is True


def test_feature_store_never_uses_realtime_display_overlay_for_training(tmp_path: Path) -> None:
    _write_market_history(tmp_path)
    outputs = tmp_path / "outputs"
    (outputs / "sn_live_snapshot.json").write_text(
        json.dumps(
            {
                "latest_quote": {"latest": 205_000, "last_close": 200_000},
                "display_overlay": {"type": "latest_quote_marker", "latest": 205_000},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = _build_with_data_dir(tmp_path)

    assert result["status"] == "success"
    manifest = result
    frame = _read_feature_frame(result)
    forbidden = {"display_overlay", "live_quote", "latest_quote", "latest_tick", "latest"}
    assert forbidden.isdisjoint(set(frame.columns))
    assert forbidden.isdisjoint(set(manifest["usable_fields"]))
    assert manifest["display_overlay_used"] is False
    assert manifest["live_quote_used_for_training"] is False


def test_stale_cross_market_data_is_excluded_from_usable_coverage(tmp_path: Path) -> None:
    _write_market_history(tmp_path)
    fundamentals = tmp_path / "outputs" / "fundamentals"
    fundamentals.mkdir(parents=True, exist_ok=True)
    (fundamentals / "sn_cross_market.json").write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "trade_date": "2026-01-01",
                        "usd_cny": 7.1,
                        "lme_tin_close": 30_000,
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = _build_with_data_dir(tmp_path)

    assert result["status"] == "success"
    manifest = result
    assert "usd_cny" not in manifest["usable_fields"]
    assert manifest["exclusion_reasons"]["usd_cny"] == "stale_after_alignment"
    assert manifest["cross_market_diagnostics"]["stale_row_count"] > 0


def test_event_available_after_trade_date_cutoff_is_not_joined(tmp_path: Path) -> None:
    _write_market_history(tmp_path)
    events = tmp_path / "outputs" / "events"
    events.mkdir(parents=True, exist_ok=True)
    (events / "event_factor_inputs.json").write_text(
        json.dumps(
            {
                "inputs": [
                    {
                        "trade_date": "2026-01-10",
                        "available_at": "2026-01-11T09:00:00+08:00",
                        "source_published_at": "2026-01-10T10:00:00+08:00",
                        "used_in_model": True,
                        "supply_shock_score": 0.8,
                        "news_count": 1,
                    }
                ],
                "manifest": {"cutoff": "2026-01-10T23:59:59+08:00"},
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    result = _build_with_data_dir(tmp_path)

    assert result["status"] == "success"
    manifest = result
    frame = _read_feature_frame(result)
    day = frame.loc[frame["trade_date"] == "2026-01-10"].iloc[0]
    assert day["supply_shock_score"] == 0.0
    assert day["_event_data_status"] == "true_zero_event"
    assert manifest["event_factor_diagnostics"]["point_in_time_rejected_count"] == 1
    assert (
        manifest["point_in_time_join_rules"]["event_factor_inputs"]
        == "exact trade_date join only when available_at <= trade_date 23:59:59 Asia/Hong_Kong"
    )
