from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.data_providers.base import ProviderResult
from sn_futures.data_layer.event_store import EventStore
from sn_futures.data_layer.intraday_store import IntradayStore
from sn_futures.data_layer.manifests import DataLayerContractError, ManifestStore
from sn_futures.data_layer.provider_result_store import load_provider_result, persist_provider_result
from sn_futures.data_layer.stores import NormalizedStore, RawStore
from sn_futures.data_layer.watermark import WatermarkStore


def _result() -> ProviderResult:
    fetched_at = "2026-06-11T09:30:00+08:00"
    source_published_at = "2026-06-10T15:00:00+08:00"
    rows = [{"trade_date": "2026-06-10", "close": 260000, "source_published_at": source_published_at}]
    normalized_rows = [
        {
            "symbol": "SN",
            "trade_date": "2026-06-10",
            "close": 260000,
            "source_published_at": source_published_at,
        }
    ]
    return ProviderResult(
        provider_id="contract_provider",
        data_kind="daily_bar",
        success=True,
        status_code="success",
        error_code="",
        rows=rows,
        normalized_rows=normalized_rows,
        fetched_at=fetched_at,
        source_timestamp=source_published_at,
        as_of=source_published_at,
        from_cache=False,
        stale=False,
        rate_limited=False,
        schema_version="provider-result-v1",
        manifest={
            "provider_id": "contract_provider",
            "data_kind": "daily_bar",
            "fetched_at": fetched_at,
            "source_published_at": source_published_at,
            "cache_status": "remote",
            "stale_status": "fresh",
            "sample_data_used": False,
            "baseline_used": False,
        },
        sanitized_error="",
    )


def _assert_real_manifest(manifest: dict[str, Any]) -> None:
    assert manifest["sample_data_used"] is False
    assert manifest["baseline_used"] is False
    assert manifest["fake_data_used"] is False
    assert manifest["demo_data_used"] is False
    assert manifest["content_hash"]
    assert manifest["fetched_at"]
    assert manifest["source_published_at"]
    assert manifest["source_published_at"] != manifest["fetched_at"]


def test_provider_result_persist_load_and_normalized_rows_are_manifested(tmp_path: Path) -> None:
    paths = persist_provider_result(_result(), output_dir=tmp_path)

    assert Path(paths["result_path"]).exists()
    assert Path(paths["status_path"]).exists()
    assert Path(paths["raw_path"]).exists()
    assert Path(paths["normalized_path"]).exists()

    loaded = load_provider_result("contract_provider", output_dir=tmp_path)
    assert loaded["provider_id"] == "contract_provider"
    assert loaded["data_kind"] == "daily_bar"
    assert loaded["normalized_rows"][0]["symbol"] == "SN"
    _assert_real_manifest(loaded["manifest"])
    assert loaded["manifest"]["allowed_for_display"] is True
    assert loaded["manifest"]["allowed_for_training"] is False
    assert loaded["manifest"]["allowed_for_prediction"] is False
    assert loaded["manifest"]["allowed_for_backtest"] is False


def test_raw_and_normalized_rows_persist_load_with_atomic_write(tmp_path: Path) -> None:
    fetched_at = "2026-06-11T09:31:00+08:00"
    source_published_at = "2026-06-10T15:00:00+08:00"
    rows = [{"trade_date": "2026-06-10", "close": 260100, "source_published_at": source_published_at}]

    raw_payload = RawStore(output_dir=tmp_path).persist(
        provider_id="local_api_provider",
        data_kind="daily_bar",
        rows=rows,
        fetched_at=fetched_at,
        source_published_at=source_published_at,
    )
    normalized_payload = NormalizedStore(output_dir=tmp_path).persist(
        provider_id="local_api_provider",
        data_kind="daily_bar",
        rows=rows,
        fetched_at=fetched_at,
        source_published_at=source_published_at,
    )

    assert RawStore(output_dir=tmp_path).load("local_api_provider", "daily_bar")["rows"] == rows
    assert NormalizedStore(output_dir=tmp_path).load("local_api_provider", "daily_bar")["rows"] == rows
    _assert_real_manifest(raw_payload["manifest"])
    _assert_real_manifest(normalized_payload["manifest"])
    assert not list((tmp_path / "data_layer").rglob("*.tmp"))


def test_watermark_merge_tracks_cache_stale_missing_and_downstream_gate(tmp_path: Path) -> None:
    store = WatermarkStore(output_dir=tmp_path)
    payload = store.merge_records(
        [
            {
                "provider_id": "local_api_provider",
                "data_kind": "daily_bar",
                "row_count": 2,
                "fetched_at": "2026-06-11T09:32:00+08:00",
                "source_published_at": "2026-06-10T15:00:00+08:00",
                "cache_status": "remote",
                "stale_status": "fresh",
                "content_hash": "abc",
            },
            {
                "provider_id": "policy_rss",
                "data_kind": "policy_event",
                "row_count": 0,
                "fetched_at": "2026-06-11T09:32:00+08:00",
                "source_published_at": "",
                "cache_status": "missing",
                "stale_status": "missing",
                "content_hash": "",
            },
            {
                "provider_id": "cache_provider",
                "data_kind": "inventory",
                "row_count": 4,
                "fetched_at": "2026-06-11T09:32:00+08:00",
                "source_published_at": "2026-06-01T15:00:00+08:00",
                "cache_status": "cache",
                "stale_status": "stale",
                "content_hash": "def",
            },
        ]
    )

    assert payload["status"] == "degraded"
    assert payload["cache_status"] == "mixed"
    assert payload["stale_status"] == "mixed"
    assert "policy_event:missing" in payload["blocking_reasons"]
    assert "inventory:stale" in payload["blocking_reasons"]
    daily = payload["records_by_kind"]["daily_bar"]
    assert daily["allowed_for_display"] is True
    assert daily["allowed_for_feature_store"] is True
    assert daily["allowed_for_training"] is True
    assert daily["allowed_for_prediction"] is True
    assert daily["allowed_for_backtest"] is True


def test_sample_fake_manifest_is_rejected_unless_fixture_is_explicitly_blocked(tmp_path: Path) -> None:
    store = ManifestStore(output_dir=tmp_path)

    with pytest.raises(DataLayerContractError):
        store.write_manifest(
            "bad_sample",
            {
                "provider_id": "bad",
                "data_kind": "daily_bar",
                "fetched_at": "2026-06-11T09:33:00+08:00",
                "source_published_at": "2026-06-10T15:00:00+08:00",
                "sample_data_used": True,
            },
        )

    fixture = store.write_manifest(
        "explicit_fixture",
        {
            "provider_id": "fixture_provider",
            "data_kind": "daily_bar",
            "fetched_at": "2026-06-11T09:33:00+08:00",
            "source_published_at": "2026-06-10T15:00:00+08:00",
            "fixture": True,
            "fake_data_used": True,
            "allowed_for_public": False,
            "allowed_for_training": False,
            "allowed_for_prediction": False,
            "allowed_for_backtest": False,
        },
        allow_fixture=True,
    )

    assert fixture["fixture"] is True
    assert fixture["allowed_for_public"] is False
    assert fixture["allowed_for_training"] is False
    assert fixture["allowed_for_prediction"] is False
    assert fixture["allowed_for_backtest"] is False


def test_latest_quote_is_display_only_and_daily_cannot_be_intraday(tmp_path: Path) -> None:
    store = IntradayStore(output_dir=tmp_path)
    quote = store.persist_latest_quote(
        provider_id="local_api_provider",
        symbol="SN",
        quote={"latest_price": 260500, "quote_time": "2026-06-11T09:34:00+08:00"},
        fetched_at="2026-06-11T09:34:01+08:00",
    )

    assert quote["manifest"]["display_only"] is True
    assert quote["manifest"]["latest_quote_display_only"] is True
    assert quote["manifest"]["allowed_for_training"] is False
    assert quote["manifest"]["allowed_for_prediction"] is False
    assert quote["manifest"]["allowed_for_backtest"] is False

    with pytest.raises(DataLayerContractError, match="daily_not_intraday"):
        store.persist_intraday_bars(
            provider_id="local_api_provider",
            symbol="SN",
            interval="1d",
            rows=[{"bar_start": "2026-06-10", "bar_end": "2026-06-11", "open": 1, "high": 1, "low": 1, "close": 1}],
            fetched_at="2026-06-11T09:35:00+08:00",
        )


def test_event_store_preserves_source_published_at_and_fetched_at_separately(tmp_path: Path) -> None:
    event = EventStore(output_dir=tmp_path).persist_event(
        provider_id="policy_rss",
        data_kind="policy_event",
        event={
            "title": "SHFE tin inventory notice",
            "url": "https://example.invalid/policy",
            "source_published_at": "2026-06-10T12:00:00+08:00",
        },
        fetched_at="2026-06-11T09:36:00+08:00",
    )

    loaded = EventStore(output_dir=tmp_path).load_events("policy_event")
    assert loaded[0]["source_published_at"] == "2026-06-10T12:00:00+08:00"
    assert loaded[0]["fetched_at"] == "2026-06-11T09:36:00+08:00"
    assert loaded[0]["source_published_at"] != loaded[0]["fetched_at"]
    assert event["manifest"]["source_published_at_coverage"] == 1.0

    missing_source = EventStore(output_dir=tmp_path).persist_event(
        provider_id="policy_rss",
        data_kind="policy_event",
        event={"title": "undated notice", "url": "https://example.invalid/undated"},
        fetched_at="2026-06-11T09:37:00+08:00",
    )
    assert missing_source["event"]["used_in_model"] is False
    assert missing_source["event"]["allowed_for_event_factor"] is False


def test_public_terminal_readiness_market_report_read_data_layer_only(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))
    output_dir = tmp_path / "outputs"
    fetched_at = "2026-06-11T09:38:00+08:00"
    source_published_at = "2026-06-10T15:00:00+08:00"
    rows = [
        {"symbol": "SN", "trade_date": "2026-06-09", "close": 259000, "source_published_at": "2026-06-09T15:00:00+08:00"},
        {"symbol": "SN", "trade_date": "2026-06-10", "close": 260000, "source_published_at": source_published_at},
    ]
    NormalizedStore(output_dir=output_dir).persist(
        provider_id="local_api_provider",
        data_kind="daily_bar",
        rows=rows,
        fetched_at=fetched_at,
        source_published_at=source_published_at,
    )
    WatermarkStore(output_dir=output_dir).merge_record(
        provider_id="local_api_provider",
        data_kind="daily_bar",
        row_count=len(rows),
        fetched_at=fetched_at,
        source_published_at=source_published_at,
        cache_status="remote",
        stale_status="fresh",
        content_hash="daily-hash",
    )
    EventStore(output_dir=output_dir).persist_event(
        provider_id="policy_rss",
        data_kind="policy_event",
        event={"title": "tin policy", "source_published_at": "2026-06-10T13:00:00+08:00"},
        fetched_at=fetched_at,
    )

    readiness_status, readiness = handle_terminal_api("/api/public-terminal/readiness", "GET", {}, None)
    market_status, market = handle_terminal_api("/api/public-terminal/market", "GET", {}, None)
    report_status, report = handle_terminal_api("/api/public-terminal/report", "GET", {}, None)

    assert readiness_status == 200
    assert market_status == 200
    assert report_status == 200
    assert readiness["data_watermark"]["schema_version"] == "data-layer-watermark-v1"
    assert market["market"]["status"] == "ready"
    assert market["market"]["chart"][-1]["close"] == 260000
    assert report["report"]["market_data_coverage"] == "ready"
    assert report["report"]["event_coverage"] == "ready"
    assert report["training_invoked"] is False
    assert report["prediction_generated"] is False
    assert report["backtest_invoked"] is False
    json.dumps({"readiness": readiness, "market": market, "report": report}, ensure_ascii=True, sort_keys=True)
