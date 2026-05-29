from __future__ import annotations

import sys

sys.path.insert(0, "src")

from sn_futures.services import market_data_service as svc


def test_akshare_history_normalizer_accepts_chinese_and_english_fields() -> None:
    rows = [
        {"日期": "2026-05-18", "开盘": "240000", "最高": "241000", "最低": "239000", "收盘": "240500", "成交量": "100", "持仓量": "200"},
        {"date": "2026-05-19", "open": 241000, "high": 242000, "low": 240000, "close": 241500, "volume": 101, "open_interest": 201},
    ]

    history = svc._normalize_history_rows(rows, source="test", symbol="SN0")

    assert len(history) == 2
    assert history[0]["close"] == 240500
    assert history[1]["open_interest"] == 201


def test_shfe_public_auxiliary_is_not_primary_realtime_failure() -> None:
    result = svc.refresh_shfe_public_aux()

    assert result["success"] is False
    assert result["status"] == "auxiliary_unavailable"
    assert "不影响主行情刷新" in result["message_zh"]

