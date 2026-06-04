from __future__ import annotations

import sys

sys.path.insert(0, "src")

import pandas as pd

from sn_futures.market_data_hub import apply_live_snapshot_overlay
from sn_futures.services import market_data_service as svc


def _history(count: int) -> list[dict[str, object]]:
    return [{"time": f"t{idx}", "close": 240000 + idx} for idx in range(count)]


def test_history_success_realtime_failed_is_history_only_success() -> None:
    merged = svc.merge_market_data(
        {"success": False, "quote": None, "attempts": []},
        {"success": True, "history": _history(80), "attempts": [], "source": "mock_history"},
        {},
        {},
    )

    assert merged["final_status"] == "history_only_success"
    assert merged["success"] is True
    assert merged["history_rows"] == 80


def test_realtime_success_history_failed_is_quote_only_partial() -> None:
    merged = svc.merge_market_data(
        {"success": True, "quote": {"latest_price": 250000, "quote_time": "2026-05-21T10:00:00", "active_contract": "SN0"}, "attempts": []},
        {"success": False, "history": [], "attempts": [], "source": ""},
        {},
        {},
    )

    assert merged["final_status"] == "quote_only_partial"
    assert merged["success"] is True
    assert "不能预测/回测" in merged["message_zh"]


def test_cache_only_when_real_sources_fail_but_cache_exists() -> None:
    merged = svc.merge_market_data(
        {"success": False, "quote": None, "attempts": []},
        {"success": False, "history": [], "attempts": [], "source": ""},
        {},
        {
            "realtime": {"latest_price": 250000, "quote_time": "2026-05-20T10:00:00", "active_contract": "SN0"},
            "history": {"history": _history(80), "generated_at": "2026-05-20T10:00:00"},
        },
    )

    assert merged["final_status"] == "cache_only"
    assert merged["from_cache"] is True


def test_shfe_auxiliary_failure_does_not_fail_main_market_data() -> None:
    merged = svc.merge_market_data(
        {"success": True, "quote": {"latest_price": 250000, "quote_time": "2026-05-21T10:00:00", "active_contract": "SN0"}, "attempts": []},
        {"success": True, "history": _history(80), "attempts": [], "source": "mock_history"},
        {"success": False, "status": "auxiliary_unavailable"},
        {},
    )

    assert merged["final_status"] == "full_success"
    assert merged["success"] is True


def test_live_snapshot_overlay_keeps_history_ohlcv_immutable() -> None:
    raw = pd.DataFrame(
        [
            {
                "date": "2026-01-01",
                "open": 100.0,
                "high": 110.0,
                "low": 90.0,
                "close": 100.0,
                "spot_price": 101.0,
                "volume": 10,
                "open_interest": 20,
            },
            {
                "date": "2026-01-02",
                "open": 102.0,
                "high": 112.0,
                "low": 92.0,
                "close": 104.0,
                "spot_price": 105.0,
                "volume": 11,
                "open_interest": 21,
            },
        ]
    )
    historical_columns = ["open", "high", "low", "close", "spot_price", "volume", "open_interest"]
    original = raw[historical_columns].copy()
    live_snapshot = {
        "generated_at": "2026-01-02T10:30:00+08:00",
        "contract_meta": {"active_contract_symbol": "nf_SN0"},
        "quotes": [
            {
                "symbol": "nf_SN0",
                "name": "SHFE SN main",
                "latest": 208.0,
                "volume": 999,
                "open_interest": 888,
            }
        ],
    }

    overlaid = apply_live_snapshot_overlay(raw, live_snapshot)

    pd.testing.assert_frame_equal(overlaid[historical_columns], original)
    overlay = overlaid.attrs["live_overlay"]
    assert overlay["history_immutable"] is True
    assert overlay["live_overlay_used_for_display_only"] is True
    assert overlay["live_overlay_used_for_training"] is False
    assert overlay["live_overlay_used_for_backtest"] is False
    assert overlay["latest_quote"]["latest"] == 208.0
    assert overlay["display_overlay"] == {
        "type": "latest_quote_marker",
        "price": 208.0,
        "quote_time": "2026-01-02T10:30:00+08:00",
        "symbol": "nf_SN0",
        "source": "live_snapshot",
    }
