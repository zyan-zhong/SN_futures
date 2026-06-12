from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.data_layer.manifests import ManifestStore
from sn_futures.data_layer.intraday_store import IntradayStore
from sn_futures.data_layer.stores import NormalizedStore
from sn_futures.data_layer.watermark import WatermarkStore
from sn_futures.public_terminal.market_indicators_service import build_market_indicators


def _daily_rows(count: int, *, start_close: float = 240000.0) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for idx in range(count):
        close = start_close + idx * 250 + (idx % 4) * 80
        rows.append(
            {
                "symbol": "SN",
                "trade_date": f"2026-05-{idx + 1:02d}" if idx < 31 else f"2026-06-{idx - 30:02d}",
                "open": close - 180,
                "high": close + 420,
                "low": close - 520,
                "close": close,
                "volume": 1000 + idx * 17,
                "open_interest": 5000 + idx * 23,
                "warehouse_warrant": 800 + idx,
                "inventory": 1800 + idx * 3,
                "source_published_at": f"2026-06-{min(idx + 1, 10):02d}T15:00:00+08:00",
            }
        )
    return rows


def _persist_daily(
    tmp_path: Path,
    rows: list[dict[str, Any]],
    *,
    stale_status: str = "fresh",
) -> None:
    output_dir = tmp_path / "outputs"
    source_published_at = rows[-1]["source_published_at"] if rows else ""
    fetched_at = "2026-06-11T09:30:00+08:00"
    NormalizedStore(output_dir=output_dir).persist(
        provider_id="local_api_provider",
        data_kind="daily_bar",
        rows=rows,
        fetched_at=fetched_at,
        source_published_at=source_published_at,
        stale_status=stale_status,
    )
    WatermarkStore(output_dir=output_dir).merge_record(
        provider_id="local_api_provider",
        data_kind="daily_bar",
        row_count=len(rows),
        fetched_at=fetched_at,
        source_published_at=source_published_at,
        cache_status="remote",
        stale_status=stale_status,
        content_hash="contract-daily-bars",
    )


def test_no_daily_bars_blocks_market_and_indicators(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))

    status, payload = handle_terminal_api("/api/public-terminal/market", "GET", {}, None)

    assert status == 200
    market = payload["market"]
    assert market["status"] == "blocked"
    assert market["reason"] == "missing_daily_bars"
    assert market["chart"] == []
    assert market["kline"]["bars"] == []
    assert market["indicators"]["status"] == "blocked"
    assert "missing_daily_bars" in market["missing_data"]["reasons"]
    assert market["sample_data_used"] is False
    assert market["customer_prediction_generated"] is False


def test_valid_daily_bars_build_watch_board_kline_and_indicators(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    rows = _daily_rows(40)
    _persist_daily(tmp_path, rows)
    IntradayStore(output_dir=tmp_path / "outputs").persist_latest_quote(
        provider_id="local_api_provider",
        symbol="SN",
        quote={"latest_price": 252300, "quote_time": "2026-06-11T09:31:00+08:00", "volume": 150},
        fetched_at="2026-06-11T09:31:05+08:00",
    )

    status, payload = handle_terminal_api("/api/public-terminal/market", "GET", {}, None)

    assert status == 200
    market = payload["market"]
    assert market["status"] == "ready"
    assert market["watch_header"]["latest_price"] == 252300
    assert market["watch_header"]["latest_quote_display_only"] is True
    assert market["watch_header"]["daily_close"] == rows[-1]["close"]
    assert market["intraday_status"]["status"] == "blocked"
    assert market["intraday_status"]["reason"] == "missing_intraday_bars"
    assert market["intraday_status"]["latest_quote_used_as_intraday_bar"] is False
    assert market["kline"]["bars"][-1]["close"] == rows[-1]["close"]
    assert market["kline"]["bars"][-1]["volume"] == rows[-1]["volume"]
    assert market["inventory"]["warehouse_warrant"] == rows[-1]["warehouse_warrant"]
    assert market["inventory"]["inventory"] == rows[-1]["inventory"]
    assert market["indicators"]["status"] == "ready"
    values = market["indicators"]["values"]
    for key in (
        "sma_5",
        "sma_20",
        "ema_12",
        "ema_26",
        "rsi_14",
        "macd",
        "macd_signal",
        "atr_14",
        "volatility_20",
        "volume_change_1",
        "open_interest_change_1",
    ):
        assert isinstance(values[key], (int, float)), key
    assert market["indicators"]["inventory_summary"]["warehouse_warrant_latest"] == rows[-1]["warehouse_warrant"]
    assert market["indicators"]["inventory_summary"]["inventory_latest"] == rows[-1]["inventory"]
    assert market["indicators"]["inventory_summary"]["warehouse_warrant_change_1"] == 1
    assert market["indicators"]["inventory_summary"]["inventory_change_1"] == 3
    manifest = market["indicators"]["manifest"]
    assert manifest["data_kind"] == "technical_indicator"
    assert "ema_12" in manifest["indicator_names"]
    assert "atr_14" in manifest["indicator_names"]
    assert manifest["sample_data_used"] is False
    assert manifest["allowed_for_training"] is False
    assert manifest["allowed_for_prediction"] is False
    assert manifest["allowed_for_backtest"] is False
    stored_manifest = ManifestStore(output_dir=tmp_path / "outputs").load_manifest("public_market_indicators")
    assert stored_manifest["data_kind"] == "technical_indicator"
    assert stored_manifest["content_hash"] == manifest["content_hash"]
    assert stored_manifest["allowed_for_training"] is False
    assert stored_manifest["allowed_for_prediction"] is False
    assert stored_manifest["allowed_for_backtest"] is False
    assert payload["prediction_generated"] is False
    json.dumps(payload, ensure_ascii=True, sort_keys=True)


def test_intraday_status_uses_real_intraday_bars_not_latest_quote(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    rows = _daily_rows(40)
    _persist_daily(tmp_path, rows)
    store = IntradayStore(output_dir=tmp_path / "outputs")
    store.persist_latest_quote(
        provider_id="local_api_provider",
        symbol="SN",
        quote={"latest_price": 252300, "quote_time": "2026-06-11T09:31:00+08:00"},
        fetched_at="2026-06-11T09:31:05+08:00",
    )
    store.persist_intraday_bars(
        provider_id="local_api_provider",
        symbol="SN",
        interval="1m",
        rows=[
            {"bar_start": "2026-06-11T09:30:00+08:00", "bar_end": "2026-06-11T09:31:00+08:00", "open": 252000, "high": 252500, "low": 251900, "close": 252300},
            {"bar_start": "2026-06-11T09:31:00+08:00", "bar_end": "2026-06-11T09:32:00+08:00", "open": 252300, "high": 252700, "low": 252100, "close": 252600},
        ],
        fetched_at="2026-06-11T09:32:05+08:00",
    )

    status, payload = handle_terminal_api("/api/public-terminal/market", "GET", {}, None)

    assert status == 200
    intraday_status = payload["market"]["intraday_status"]
    assert intraday_status["status"] == "ready"
    assert intraday_status["interval"] == "1m"
    assert intraday_status["row_count"] == 2
    assert intraday_status["latest_bar_time"] == "2026-06-11T09:32:00+08:00"
    assert intraday_status["latest_quote_used_as_intraday_bar"] is False
    assert intraday_status["daily_bar_used_as_intraday"] is False
    assert payload["market"]["latest_quote"]["latest_price"] == 252300


def test_stale_daily_bars_are_displayable_but_prediction_denied(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    rows = _daily_rows(40)
    _persist_daily(tmp_path, rows, stale_status="stale")

    status, payload = handle_terminal_api("/api/public-terminal/market", "GET", {}, None)

    assert status == 200
    market = payload["market"]
    assert market["status"] == "stale"
    assert market["chart"]
    assert market["data_watermark_panel"]["display_allowed"] is True
    assert market["data_watermark_panel"]["prediction_allowed"] is False
    assert market["indicators"]["manifest"]["allowed_for_prediction"] is False
    assert "stale_daily_bars" in market["missing_data"]["reasons"]


def test_indicators_block_when_bars_are_insufficient(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    rows = _daily_rows(3)
    _persist_daily(tmp_path, rows)

    indicators = build_market_indicators(rows)
    status, payload = handle_terminal_api("/api/public-terminal/market", "GET", {}, None)

    assert indicators["status"] == "blocked"
    assert indicators["values"] == {}
    assert "insufficient_bars_for_indicators" in indicators["blocking_reasons"]
    assert payload["market"]["status"] == "ready"
    assert payload["market"]["indicators"]["status"] == "blocked"
    assert payload["market"]["indicators"]["values"] == {}
    assert payload["market"]["kline"]["bars"]


def test_public_market_never_displays_sample_chart_from_corrupt_data_layer(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    output_dir = tmp_path / "outputs"
    path = output_dir / "data_layer" / "normalized" / "sample_provider" / "daily_bar.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "rows": [
                    {
                        "symbol": "SN",
                        "trade_date": "2026-06-10",
                        "close": 250000,
                        "sample": True,
                        "source_published_at": "2026-06-10T15:00:00+08:00",
                    }
                ],
                "manifest": {
                    "provider_id": "sample_provider",
                    "data_kind": "daily_bar",
                    "sample_data_used": True,
                    "source_published_at": "2026-06-10T15:00:00+08:00",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    status, payload = handle_terminal_api("/api/public-terminal/market", "GET", {}, None)

    assert status == 200
    assert payload["market"]["status"] == "blocked"
    assert payload["market"]["chart"] == []
    assert payload["market"]["kline"]["bars"] == []
    assert payload["market"]["sample_data_used"] is False
    assert "sample" not in json.dumps(payload["market"]["chart"], ensure_ascii=False).lower()
