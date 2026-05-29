from __future__ import annotations

import sys
from datetime import datetime, timedelta

sys.path.insert(0, "src")

from sn_futures.services.freshness_policy import classify_freshness, is_stale


def test_miit_policy_ttl_is_seven_days() -> None:
    now = datetime(2026, 5, 21, 12, 0, 0)
    result = classify_freshness("miit_policy", now - timedelta(days=6), now=now)
    assert result["ttl_seconds"] == 7 * 24 * 60 * 60
    assert result["status_code"] == "ok"
    assert result["stale"] is False


def test_newsapi_unconfigured_is_not_stale() -> None:
    result = classify_freshness("newsapi", None, enabled=False, success=False)
    assert result["status_code"] == "unconfigured"
    assert result["status_zh"] == "未配置"
    assert result["stale"] is False


def test_shfe_public_non_trading_day_can_wait_instead_of_failure() -> None:
    now = datetime(2026, 5, 21, 12, 0, 0)
    result = classify_freshness("realtime_market", now - timedelta(hours=2), trading_session="closed", now=now)
    assert result["status_code"] == "waiting_next_session"
    assert result["stale"] is False


def test_stale_true_for_expired_daily_source() -> None:
    now = datetime(2026, 5, 21, 12, 0, 0)
    assert is_stale("daily_market", now - timedelta(days=3), now=now) is True
