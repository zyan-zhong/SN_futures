from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.data_layer.provider_result_store import load_provider_result
from sn_futures.data_layer.watermark import WatermarkStore
from sn_futures.public_terminal.market_service import build_public_market
from sn_futures.public_terminal.provider_closed_loop_service import record_provider_closed_loop_result
from sn_futures.public_terminal.provider_smoke_result_bridge_service import bridge_provider_smoke_result
from sn_futures.public_terminal.readiness_service import build_public_terminal_readiness
from sn_futures.public_terminal.refresh_orchestrator import run_public_refresh_data_status
from sn_futures.public_terminal.report_service import build_public_report


PROVIDERS = (
    "alpha_vantage",
    "newsapi",
    "akshare_news",
    "tushare_futures",
    "shfe_public",
    "public_policy_rss",
    "local_api_provider",
)

SCENARIOS = (
    "not_configured",
    "skipped_no_remote",
    "timeout",
    "rate_limited",
    "no_rows",
    "malformed",
    "valid_fake_rows",
)

DOWNSTREAM_FALSE = (
    "feature_store_written",
    "production_cache_written",
    "training_invoked",
    "prediction_generated",
    "backtest_invoked",
    "active_updated",
    "customer_prediction_generated",
)

MARKET_PROVIDERS = {"alpha_vantage", "local_api_provider"}
EVENT_PROVIDERS = {"newsapi", "akshare_news", "public_policy_rss"}


def _valid_rows(provider_id: str) -> list[dict[str, Any]]:
    if provider_id in MARKET_PROVIDERS:
        return [
            {
                "symbol": "SN",
                "trade_date": "2026-06-10",
                "open": 259000,
                "high": 261000,
                "low": 258000,
                "close": 260000,
                "source_published_at": "2026-06-10T15:00:00+08:00",
            }
        ]
    if provider_id in EVENT_PROVIDERS:
        return [
            {
                "title": f"{provider_id} tin supply update",
                "url": f"https://example.invalid/{provider_id}/tin",
                "source_published_at": "2026-06-10T12:00:00+08:00",
            }
        ]
    if provider_id == "tushare_futures":
        return [
            {
                "ts_code": "SN.SHF",
                "trade_date": "20260610",
                "warehouse_warrant": 1200,
                "source_published_at": "2026-06-10T15:00:00+08:00",
            }
        ]
    return [
        {
            "symbol": "SN",
            "trade_date": "2026-06-10",
            "inventory": 1200,
            "source_published_at": "2026-06-10T15:00:00+08:00",
        }
    ]


def _smoke_payload(provider_id: str, scenario: str) -> dict[str, Any]:
    fetched_at = "2026-06-11T09:30:00+08:00"
    if scenario == "valid_fake_rows":
        rows = _valid_rows(provider_id)
        return {
            "provider_id": provider_id,
            "provider": provider_id,
            "status": "pass",
            "success": True,
            "row_count": len(rows),
            "rows": rows,
            "normalized_rows": rows,
            "fetched_at": fetched_at,
            "source_timestamp": rows[-1]["source_published_at"],
            "manifest": {
                "provider_id": provider_id,
                "row_count": len(rows),
                "normalized_row_count": len(rows),
                "fetched_at": fetched_at,
                "source_published_at": rows[-1]["source_published_at"],
                "cache_status": "remote",
                "stale_status": "fresh",
                "sample_data_used": False,
                "baseline_used": False,
            },
        }
    error_code = {
        "not_configured": "not_configured",
        "skipped_no_remote": "skipped_no_remote",
        "timeout": "request_timeout",
        "rate_limited": "rate_limited",
        "no_rows": "no_rows",
        "malformed": "malformed_response",
    }[scenario]
    return {
        "provider_id": provider_id,
        "provider": provider_id,
        "status": "blocked",
        "success": False,
        "error_code": error_code,
        "row_count": 0,
        "rows": [],
        "normalized_rows": [],
        "fetched_at": fetched_at,
        "manifest": {
            "provider_id": provider_id,
            "fetched_at": fetched_at,
            "row_count": 0,
            "normalized_row_count": 0,
            "blocking_reasons": [error_code],
            "cache_status": "missing",
            "stale_status": "missing",
            "sample_data_used": False,
            "baseline_used": False,
        },
    }


def _provider_record(watermark: dict[str, Any], provider_id: str) -> dict[str, Any]:
    for record in watermark.get("records", []):
        if isinstance(record, dict) and record.get("provider_id") == provider_id:
            return record
    raise AssertionError(f"missing watermark record for {provider_id}: {watermark}")


@pytest.mark.parametrize("provider_id", PROVIDERS)
@pytest.mark.parametrize("scenario", SCENARIOS)
def test_each_provider_status_closes_loop_to_data_layer_manifest_and_watermark(
    provider_id: str,
    scenario: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))

    closed_loop = record_provider_closed_loop_result(_smoke_payload(provider_id, scenario), source="contract_test")

    result = load_provider_result(provider_id)
    assert result["provider_id"] == provider_id
    assert result["manifest"]["sample_data_used"] is False
    assert result["manifest"]["baseline_used"] is False
    assert result["manifest"]["content_hash"]
    for flag in DOWNSTREAM_FALSE:
        assert result["manifest"].get(flag) is False, (provider_id, scenario, flag)
    assert result["manifest"]["allowed_for_training"] is False
    assert result["manifest"]["allowed_for_prediction"] is False
    assert result["manifest"]["allowed_for_backtest"] is False

    watermark = WatermarkStore().load()
    record = _provider_record(watermark, provider_id)
    assert record["provider_id"] == provider_id
    assert record["sample_data_used"] is False
    assert record["baseline_used"] is False
    assert closed_loop["data_watermark"]["schema_version"] == "data-layer-watermark-v1"

    readiness = build_public_terminal_readiness()
    assert readiness["data_watermark"]["schema_version"] == "data-layer-watermark-v1"
    assert provider_id in json.dumps(readiness["provider_status"], ensure_ascii=False)

    refresh = run_public_refresh_data_status()
    if scenario == "valid_fake_rows":
        assert result["success"] is True
        assert record["status"] == "ready"
        assert refresh["status"] == "success"
        assert refresh["result"]["data_watermark_updated"] is True
        assert provider_id in json.dumps(refresh["provider_coverage"], ensure_ascii=False)
    else:
        assert result["success"] is False
        assert record["status"] in {"missing", "stale"}
        assert refresh["status"] == "blocked"
        assert result["error_code"] in json.dumps(record["blocking_reasons"], ensure_ascii=False)


@pytest.mark.parametrize("provider_id", PROVIDERS)
def test_valid_provider_closed_loop_feeds_public_readiness_refresh_market_or_report(
    provider_id: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))

    record_provider_closed_loop_result(_smoke_payload(provider_id, "valid_fake_rows"), source="contract_test")
    readiness = build_public_terminal_readiness()
    refresh = run_public_refresh_data_status()
    market = build_public_market()
    report = build_public_report()

    assert readiness["provider_smoke_passed"] is True
    assert provider_id in readiness["provider_status"]["passed_providers"]
    assert refresh["status"] == "success"
    assert refresh["training_invoked"] is False
    assert refresh["prediction_generated"] is False
    assert refresh["backtest_invoked"] is False
    if provider_id in MARKET_PROVIDERS:
        assert market["market"]["status"] == "ready"
        assert market["market"]["chart"][-1]["close"] == 260000
        assert report["report"]["market_data_coverage"] == "ready"
    elif provider_id in EVENT_PROVIDERS:
        assert market["market"]["status"] == "blocked"
        assert report["report"]["event_coverage"] == "ready"
    else:
        assert market["market"]["status"] == "blocked"
        assert report["report"]["provider_status"] in {"ready", "degraded"}


def test_legacy_provider_bridge_writes_data_layer_provider_result_and_watermark(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))

    report = bridge_provider_smoke_result(_smoke_payload("newsapi", "valid_fake_rows"), source="legacy_provider_test")

    assert report["passed_count"] == 1
    result = load_provider_result("newsapi")
    assert result["provider_id"] == "newsapi"
    assert result["success"] is True
    watermark = WatermarkStore().load()
    assert _provider_record(watermark, "newsapi")["status"] == "ready"


def test_public_provider_smoke_defaults_to_no_remote_and_still_writes_closed_loop(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SN_DATA_DIR", str(tmp_path))

    status, payload = handle_terminal_api(
        "/api/public-terminal/provider-smoke",
        "POST",
        {},
        {"provider": "alpha_vantage"},
    )

    assert status == 200
    assert payload["providers"][0]["provider_id"] == "alpha_vantage"
    assert payload["providers"][0]["error_code"] == "skipped_no_remote"
    result = load_provider_result("alpha_vantage")
    assert result["error_code"] == "skipped_no_remote"
    assert result["manifest"]["allow_remote"] is False
    assert WatermarkStore().load()["schema_version"] == "data-layer-watermark-v1"
