from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.data_source_coverage_improvement_service import improve_real_data_source_coverage


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_market_history(output_dir: Path, rows: int = 160) -> list[str]:
    dates = [f"2026-01-{(idx % 28) + 1:02d}" if idx < 28 else f"2026-02-{((idx - 28) % 28) + 1:02d}" if idx < 56 else f"2026-03-{((idx - 56) % 28) + 1:02d}" if idx < 84 else f"2026-04-{((idx - 84) % 28) + 1:02d}" if idx < 112 else f"2026-05-{((idx - 112) % 28) + 1:02d}" if idx < 140 else f"2026-06-{((idx - 140) % 20) + 1:02d}" for idx in range(rows)]
    history = []
    for idx, day in enumerate(dates):
        close = 250000 + idx
        history.append({"trade_date": day, "open": close - 30, "high": close + 80, "low": close - 90, "close": close, "volume": 1000 + idx})
    _write_json(output_dir / "sn_market_history.json", {"sample": False, "history": history})
    return dates


def _write_daily_market_history(output_dir: Path, rows: int = 140) -> list[str]:
    start = date(2026, 1, 1)
    dates = [(start + timedelta(days=idx)).isoformat() for idx in range(rows)]
    history = []
    for idx, day in enumerate(dates):
        close = 250000 + idx * 5
        history.append({"trade_date": day, "open": close - 30, "high": close + 80, "low": close - 90, "close": close, "volume": 1000 + idx})
    _write_json(output_dir / "sn_market_history.json", {"sample": False, "history": history})
    return dates


class FakeTushareClient:
    def __init__(self, dates: list[str]) -> None:
        self.dates = dates

    def fut_basic(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"ts_code": "SN2606.SHF", "symbol": "SN2606", "name": "SN Tin", "exchange": "SHFE"}])

    def trade_cal(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"cal_date": day, "is_open": 1, "exchange": "SHFE"} for day in self.dates])

    def fut_daily(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"trade_date": day, "ts_code": "SN2606.SHF", "open": 1, "high": 2, "low": 1, "close": 2, "settle": 2, "vol": 100 + idx, "oi": 40000 + idx}
                for idx, day in enumerate(self.dates)
            ]
        )

    def fut_wsr(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": day, "product": "SN", "warehouse_receipt": 4000 + idx} for idx, day in enumerate(self.dates)])

    def fut_settle(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame([{"trade_date": day, "ts_code": "SN2606.SHF", "settle": 250000 + idx, "margin_rate": 0.12, "fee_rate": 3.0} for idx, day in enumerate(self.dates)])

    def fut_holding(self, **_: object) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {"trade_date": day, "ts_code": "SN2606.SHF", "broker": "member", "long_hld": 20000 + idx, "short_hld": 18000 + idx, "vol": 100, "rank": 1}
                for idx, day in enumerate(self.dates)
            ]
        )


class FakeManagedClient:
    def __init__(self, dates: list[str]) -> None:
        self.dates = dates

    def get_json(self, path: str, headers: dict[str, str]) -> dict[str, object]:
        assert path.startswith("/api/sn/fundamentals/history?")
        assert headers.get("X-SN-License-Token")
        rows = [
            {
                "trade_date": day,
                "symbol": "SN",
                "spot_price": 251000 + idx,
                "spot_premium": 120 + idx,
                "spot_futures_basis": 500 + idx,
                "shfe_inventory": 8000 + idx,
                "shfe_warehouse_receipt": 4100 + idx,
                "lme_tin_close": 33500 + idx,
                "lme_inventory": 4700 + idx,
                "near_contract": "SN2606",
                "far_contract": "SN2607",
                "near_contract_close": 250000 + idx,
                "far_contract_close": 249000 + idx,
                "near_open_interest": 42000 + idx,
                "far_open_interest": 36000 + idx,
                "main_contract": "SN2606",
                "main_contract_switch_flag": 0,
            }
            for idx, day in enumerate(self.dates)
        ]
        return {"status": "success", "rows": rows}


class FakeAlphaProvider:
    api_key = "configured"

    def __init__(self, dates: list[str]) -> None:
        self.dates = dates

    def fetch_fx_daily(self, **_: object) -> dict[str, object]:
        return {
            "success": True,
            "data": {"Time Series FX (Daily)": {day: {"4. close": str(7.0 + idx * 0.001)} for idx, day in enumerate(self.dates)}},
        }

    def fetch_treasury_yield(self, **_: object) -> dict[str, object]:
        return {"success": True, "data": {"data": [{"date": day, "value": str(4.0 + idx * 0.001)} for idx, day in enumerate(self.dates)]}}

    def fetch_commodity_proxy(self, *_: object, **__: object) -> dict[str, object]:
        return {"success": True, "data": {"data": [{"date": day, "value": str(9500 + idx)} for idx, day in enumerate(self.dates)]}}


class FakeNewsProvider:
    def __init__(self, event_date: str) -> None:
        self.event_date = event_date

    def fetch_tin_news(self, **_: object) -> dict[str, object]:
        return {
            "configured": True,
            "enabled": True,
            "success": True,
            "from_cache": False,
            "articles": [
                {
                    "title": "SHFE tin warehouse warrant declines as Myanmar mine supply tightens",
                    "description": "LME tin and SHFE tin inventory pressure supports supply shock monitoring.",
                    "publishedAt": f"{self.event_date}T09:30:00Z",
                    "source": {"name": "Reuters"},
                    "url": "https://example.com/sn-tin-supply",
                    "query_group": "exchange_inventory",
                    "query_language": "en",
                    "query_sort_by": "relevancy",
                    "query_window_days": 7,
                }
            ],
            "query_attempts": [],
            "row_count": 1,
            "message_zh": "NewsAPI 获取成功。",
        }


class FakeRateLimitedNewsProvider:
    def fetch_tin_news(self, **_: object) -> dict[str, object]:
        return {
            "configured": True,
            "enabled": True,
            "success": False,
            "from_cache": False,
            "articles": [],
            "query_attempts": [{"status": "error", "error": "rateLimited: quota exceeded"}],
            "row_count": 0,
            "error_code": "rate_limited",
            "message_zh": "NewsAPI rate limited.",
            "error_message_zh": "rateLimited: quota exceeded",
            "next_actions_zh": ["等待 NewsAPI quota 冷却后重试。"],
        }


class DataSourceCoverageImprovementServiceTest(unittest.TestCase):
    def test_missing_credentials_are_explicit_and_no_model_outputs_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_TUSHARE_TOKEN": "",
                "SN_MANAGED_DATA_PROXY_TOKEN": "",
                "SN_MANAGED_DATA_PROXY_URL": "",
                "SN_MANAGED_DATA_PROXY_ENABLED": "",
                "SN_ALPHA_VANTAGE_KEY": "",
                "SN_NEWSAPI_KEY": "",
            },
            clear=False,
        ):
            output_dir = Path(tmp) / "outputs"
            _write_market_history(output_dir)

            report = improve_real_data_source_coverage(force=False)

            self.assertEqual(report["status"], "success")
            self.assertEqual(report["source_status"]["tushare"]["status"], "token_missing")
            self.assertEqual(report["source_status"]["managed_proxy"]["status"], "disabled")
            self.assertIn(report["source_status"]["alpha"]["status"], {"key_missing", "using_cache"})
            self.assertIn(report["source_status"]["newsapi"]["status"], {"skipped", "not_configured"})
            self.assertFalse(report["active_updated"])
            self.assertFalse(report["customer_prediction_generated"])
            self.assertFalse(report["training_invoked"])
            self.assertTrue((output_dir / "diagnostics" / "data_source_coverage_improvement.json").exists())
            self.assertTrue((output_dir / "diagnostics" / "data_source_coverage_improvement.md").exists())
            for forbidden in [
                output_dir / "model_registry" / "active_model.json",
                output_dir / "sn_live_predictions.json",
                output_dir / "customer_predictions.json",
            ]:
                self.assertFalse(forbidden.exists(), str(forbidden))

    def test_configured_sources_raise_coverage_and_enter_feature_store_v5(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_TUSHARE_TOKEN": "tushare-token",
                "SN_MANAGED_DATA_PROXY_TOKEN": "managed-token",
                "SN_MANAGED_DATA_PROXY_URL": "https://managed.example",
                "SN_MANAGED_DATA_PROXY_ENABLED": "1",
                "SN_ALPHA_VANTAGE_KEY": "alpha-token",
                "SN_NEWSAPI_KEY": "news-token",
            },
            clear=False,
        ):
            output_dir = Path(tmp) / "outputs"
            dates = _write_daily_market_history(output_dir)

            report = improve_real_data_source_coverage(
                force=True,
                tushare_client=FakeTushareClient(dates),
                managed_client=FakeManagedClient(dates),
                alpha_provider=FakeAlphaProvider(dates),
                news_provider=FakeNewsProvider(dates[30]),
            )

            self.assertEqual(report["source_status"]["tushare"]["status"], "success")
            self.assertEqual(report["source_status"]["managed_proxy"]["status"], "success")
            self.assertEqual(report["source_status"]["alpha"]["status"], "success")
            self.assertEqual(report["source_status"]["newsapi"]["status"], "success")
            self.assertGreater(report["feature_coverage_delta"]["basis"]["after"], report["feature_coverage_delta"]["basis"]["before"])
            self.assertGreater(report["feature_coverage_delta"]["inventory"]["after"], report["feature_coverage_delta"]["inventory"]["before"])
            self.assertGreater(report["feature_coverage_delta"]["cross_market"]["after"], report["feature_coverage_delta"]["cross_market"]["before"])
            artifact = json.loads(Path(report["json_path"]).read_text(encoding="utf-8"))
            self.assertEqual(artifact["source_status"]["tushare"]["status"], "success")
            self.assertNotIn("features", artifact["feature_coverage_after"]["groups"][0])

            manifest = report["feature_store_v5"]
            usable = set(manifest["usable_fields"])
            for field in ["open_interest", "warehouse_receipt_delta_1w", "member_net_position", "spot_futures_basis", "shfe_inventory_delta_1w", "lme_tin_return_1d", "near_far_spread", "usd_cny_return", "us10y_change", "supply_shock_score"]:
                self.assertIn(field, usable)
            self.assertFalse(report["training_invoked"])
            self.assertFalse(report["active_updated"])
            self.assertFalse(report["customer_prediction_generated"])

    def test_newsapi_rate_limit_preserves_cached_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_TUSHARE_TOKEN": "",
                "SN_MANAGED_DATA_PROXY_TOKEN": "",
                "SN_MANAGED_DATA_PROXY_URL": "",
                "SN_ALPHA_VANTAGE_KEY": "",
                "SN_NEWSAPI_KEY": "news-token",
            },
            clear=False,
        ):
            output_dir = Path(tmp) / "outputs"
            dates = _write_daily_market_history(output_dir)
            cached_event = {
                "title": "SHFE tin inventory decline",
                "description": "SHFE tin warehouse warrant decline and LME tin supply shock.",
                "published_at": f"{dates[10]}T09:30:00Z",
                "source": "Reuters",
                "url": "https://example.com/cached-news",
                "query_group": "exchange_inventory",
                "used_in_model": True,
                "relevance_score": 0.9,
                "supply_chain_score": 0.8,
                "inventory_score": 0.7,
                "source_reliability_score": 0.9,
            }
            _write_json(output_dir / "events" / "news_events.json", {"events": [cached_event], "generated_at": "2026-05-30T10:00:00"})
            _write_json(output_dir / "events" / "news_raw.json", {"articles": [cached_event], "generated_at": "2026-05-30T10:00:00"})

            report = improve_real_data_source_coverage(force=True, news_provider=FakeRateLimitedNewsProvider())

            self.assertEqual(report["source_status"]["newsapi"]["status"], "using_cache")
            self.assertTrue(report["source_status"]["newsapi"]["from_cache"])
            cached_after = json.loads((output_dir / "events" / "news_events.json").read_text(encoding="utf-8"))
            self.assertEqual(len(cached_after["events"]), 1)
            self.assertIn("SHFE tin inventory decline", cached_after["events"][0]["title"])
            self.assertIn("supply_shock_score", report["feature_store_v5"]["usable_fields"])


if __name__ == "__main__":
    unittest.main()
