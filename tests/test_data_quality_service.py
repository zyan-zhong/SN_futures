from __future__ import annotations

import sys

sys.path.insert(0, "src")

from sn_futures.services.data_quality_service import compute_data_quality_score


def test_data_quality_not_fixed_at_sixty_percent() -> None:
    low = compute_data_quality_score({"latest_price": None, "history_rows": 0, "prediction_count": 0})
    high = compute_data_quality_score(
        {
            "latest_price": 250000,
            "quote_time": "2026-05-21T10:00:00",
            "history_rows": 80,
            "news_configured": True,
            "news_count": 5,
            "event_count": 5,
            "report_count": 4,
            "prediction_count": 7,
            "model_status": "active",
        }
    )
    assert low["score"] != high["score"]
    assert low["score"] != 0.6
    assert high["score"] > 0.8
    assert high["label"] in {"优秀", "可用"}


def test_sample_mode_does_not_count_as_real_quality() -> None:
    result = compute_data_quality_score({"sample_mode": True})
    assert result["score"] == 0.0
    assert result["label"] == "样例数据"
    assert "sample_quality" in result["components"]


def test_cache_market_quality_is_discounted() -> None:
    result = compute_data_quality_score({"latest_price": 250000, "quote_time": "2026-05-21T10:00:00", "from_cache": True, "history_rows": 80})
    assert result["components"]["market_latest_score"]["score"] < 1.0
    assert any("缓存" in reason for reason in result["degradation_reasons"])
