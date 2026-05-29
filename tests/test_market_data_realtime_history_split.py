from __future__ import annotations

import sys

sys.path.insert(0, "src")

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

