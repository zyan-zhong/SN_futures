from __future__ import annotations

import importlib
import json
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from sn_futures.data_providers.akshare_news_provider import AkShareNewsProvider
from sn_futures.data_providers.provider_registry import build_provider_registry


class EmptyAkShareNews:
    def futures_news_shmet(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()

    def stock_info_global_cls(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()


class MissingAkShareNewsFunctions:
    pass


class MalformedAkShareNews:
    def futures_news_shmet(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame([{"foo": "bar"}])

    def stock_info_global_cls(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame([{"foo": "bar"}])


class ValidAkShareNews:
    def futures_news_shmet(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "标题": "SHFE tin warehouse warrants drop after Indonesia tin export delay",
                    "内容": "LME tin and Shanghai tin futures react to lower inventory and supply disruption.",
                    "发布日期": "2026-06-04",
                    "发布时间": "09:30:00",
                }
            ]
        )

    def stock_info_global_cls(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                {
                    "标题": "Myanmar tin mine suspension tightens SHFE tin supply",
                    "内容": "Shanghai tin futures and LME tin prices monitor mine disruption.",
                    "发布日期": "2026-06-04",
                    "发布时间": "10:15:00",
                }
            ]
        )


def _valid_row(title: str, published_at: str = "2026-06-04T09:30:00+08:00") -> dict[str, str]:
    return {
        "title": title,
        "content": "SHFE tin, LME tin, warehouse warrants and Indonesia tin supply remain relevant.",
        "source_published_at": published_at,
    }


class PartialTimeoutAkShareNews:
    def futures_news_shmet(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame([_valid_row("SHFE tin warehouse warrants tighten after Indonesia export delay")])

    def stock_info_global_cls(self, symbol: str) -> pd.DataFrame:
        time.sleep(5)
        return pd.DataFrame([_valid_row("This row should never be returned")])


class AllTimeoutAkShareNews:
    def futures_news_shmet(self, symbol: str) -> pd.DataFrame:
        time.sleep(5)
        return pd.DataFrame([_valid_row("This row should never be returned")])

    def stock_info_global_cls(self, symbol: str) -> pd.DataFrame:
        time.sleep(5)
        return pd.DataFrame([_valid_row("This row should never be returned")])


class LargeAkShareNews:
    def futures_news_shmet(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                _valid_row(f"SHFE tin source row {idx}", f"2026-06-04T09:{idx:02d}:00+08:00")
                for idx in range(5)
            ]
        )

    def stock_info_global_cls(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame(
            [
                _valid_row(f"CLS tin source row {idx}", f"2026-06-04T10:{idx:02d}:00+08:00")
                for idx in range(5)
            ]
        )


class SecretLeakingAkShareNews:
    def futures_news_shmet(self, symbol: str) -> pd.DataFrame:
        raise RuntimeError("Authorization Bearer secret-akshare-token path C:/Users/Henry/secrets.json")

    def stock_info_global_cls(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()


class DeterministicAkShareTimeoutExecutor:
    def __init__(self, *, timeout_functions: set[str]) -> None:
        self.timeout_functions = set(timeout_functions)

    def __call__(
        self,
        ak_module: object,
        function_name: str,
        params_list: list[dict[str, object]],
        timeout_seconds: float | None,
    ) -> dict[str, list[object]]:
        del ak_module, params_list, timeout_seconds
        if function_name in self.timeout_functions:
            return {
                "rows": [],
                "errors": [
                    {
                        "error_code": "request_timeout",
                        "message": f"request_timeout: {function_name} timed out in deterministic contract executor",
                        "timed_out": True,
                    }
                ],
            }
        if function_name == "futures_news_shmet":
            return {"rows": [_valid_row("SHFE tin warehouse warrants tighten after Indonesia export delay")], "errors": []}
        return {"rows": [_valid_row("CLS tin source row")], "errors": []}


class AkShareNewsProviderContractTest(unittest.TestCase):
    def test_missing_akshare_import_returns_structured_status(self) -> None:
        real_import = importlib.import_module

        def fake_import(name: str, package: str | None = None):
            if name == "akshare":
                raise ImportError("akshare unavailable")
            return real_import(name, package)

        with patch("importlib.import_module", fake_import):
            result = AkShareNewsProvider().fetch()

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "akshare_import_failed")
        self.assertEqual(result.rows, [])
        self.assertEqual(result.normalized_rows, [])
        self.assertIn("akshare_import_failed", result.manifest["blocking_reasons"][0])

    def test_missing_akshare_functions_are_api_changed_not_success(self) -> None:
        result = AkShareNewsProvider(ak_module=MissingAkShareNewsFunctions()).fetch()

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "akshare_api_changed")
        self.assertEqual(result.normalized_rows, [])
        self.assertEqual(result.manifest["row_count"], 0)

    def test_empty_dataframes_are_no_rows_and_not_success(self) -> None:
        result = AkShareNewsProvider(ak_module=EmptyAkShareNews()).fetch()

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "no_rows")
        self.assertEqual(result.rows, [])
        self.assertEqual(result.normalized_rows, [])
        self.assertEqual(result.manifest["cache_status"], "missing")

    def test_malformed_dataframe_is_structured_error_without_normalized_rows(self) -> None:
        result = AkShareNewsProvider(ak_module=MalformedAkShareNews()).fetch()

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "missing_required_columns")
        self.assertGreater(len(result.rows), 0)
        self.assertEqual(result.normalized_rows, [])
        self.assertIn("missing_required_columns", result.sanitized_error)

    def test_valid_shmet_and_cls_rows_emit_event_records_with_source_time(self) -> None:
        result = AkShareNewsProvider(ak_module=ValidAkShareNews()).fetch()

        self.assertTrue(result.success)
        self.assertEqual(result.error_code, "")
        self.assertEqual(len(result.normalized_rows), 2)
        providers = {row["provider"] for row in result.normalized_rows}
        self.assertEqual(providers, {"akshare_shmet", "akshare_cls"})
        for row in result.normalized_rows:
            self.assertEqual(row["data_kind"], "news")
            self.assertIn("event_id", row)
            self.assertIn("content_hash", row)
            self.assertNotEqual(row["source_published_at"], "")
            self.assertNotEqual(row["fetched_at"], "")
            self.assertNotEqual(row["source_published_at"], row["fetched_at"])
            self.assertEqual(row["available_at"], row["source_published_at"])
            self.assertEqual(row["event_time_confidence"], 1.0)
        self.assertEqual(result.manifest["source_published_at_coverage"], 1.0)
        self.assertFalse(result.manifest["sample_data_used"])
        self.assertFalse(result.manifest["baseline_used"])

    def test_one_source_timeout_returns_quickly_with_partial_success_manifest(self) -> None:
        started = time.perf_counter()
        result = AkShareNewsProvider(
            ak_module=ValidAkShareNews(),
            call_timeout_seconds=2.0,
            source_call_executor=DeterministicAkShareTimeoutExecutor(timeout_functions={"stock_info_global_cls"}),
        ).fetch()
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 8.0)
        self.assertTrue(result.success)
        self.assertGreater(len(result.normalized_rows), 0)
        self.assertEqual({row["provider"] for row in result.normalized_rows}, {"akshare_shmet"})
        statuses = result.manifest["source_statuses"]
        self.assertEqual(len(statuses), 2)
        timeout_status = next(item for item in statuses if item["provider_id"] == "akshare_cls")
        self.assertFalse(timeout_status["success"])
        self.assertEqual(timeout_status["error_code"], "request_timeout")
        self.assertTrue(timeout_status["timed_out"])
        self.assertGreaterEqual(timeout_status["elapsed_seconds"], 0.0)
        self.assertIn("partial_source_failures", result.manifest)
        self.assertEqual(result.manifest["partial_source_failures"][0]["provider_id"], "akshare_cls")

    def test_all_sources_timeout_fails_with_source_statuses_and_no_downstream_outputs(self) -> None:
        started = time.perf_counter()
        result = AkShareNewsProvider(
            ak_module=ValidAkShareNews(),
            call_timeout_seconds=2.0,
            source_call_executor=DeterministicAkShareTimeoutExecutor(
                timeout_functions={"futures_news_shmet", "stock_info_global_cls"}
            ),
        ).fetch()
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 8.0)
        self.assertFalse(result.success)
        self.assertIn(result.error_code, {"request_timeout", "network_failed", "all_sources_failed"})
        self.assertEqual(result.normalized_rows, [])
        statuses = result.manifest["source_statuses"]
        self.assertEqual(len(statuses), 2)
        self.assertTrue(all(item["timed_out"] for item in statuses))
        self.assertTrue(all(item["error_code"] == "request_timeout" for item in statuses))
        self.assertFalse(result.manifest["feature_store_written"])
        self.assertFalse(result.manifest["training_invoked"])
        self.assertFalse(result.manifest["backtest_invoked"])
        self.assertFalse(result.manifest["customer_prediction_generated"])
        self.assertIn("request_timeout", result.manifest["blocking_reasons"][0])

    def test_max_rows_per_source_limits_smoke_volume_without_merging_publish_time(self) -> None:
        result = AkShareNewsProvider(
            ak_module=LargeAkShareNews(),
            max_rows_per_source=2,
        ).fetch()

        self.assertTrue(result.success)
        self.assertLessEqual(len(result.normalized_rows), 4)
        statuses = result.manifest["source_statuses"]
        self.assertTrue(all(item["row_count"] <= 2 for item in statuses))
        self.assertTrue(all(item["max_rows_per_source"] == 2 for item in statuses))
        self.assertTrue(all(item["limited"] for item in statuses))
        for row in result.normalized_rows:
            self.assertNotEqual(row["source_published_at"], "")
            self.assertNotEqual(row["source_published_at"], row["fetched_at"])

    def test_errors_are_sanitized_and_do_not_trigger_downstream_outputs(self) -> None:
        result = AkShareNewsProvider(
            ak_module=SecretLeakingAkShareNews(),
            secret_values=["secret-akshare-token"],
        ).fetch()
        encoded = json.dumps(result.to_dict(), ensure_ascii=False)

        self.assertFalse(result.success)
        self.assertNotIn("secret-akshare-token", encoded)
        self.assertNotIn("C:/Users/Henry", encoded)
        self.assertFalse(result.manifest["feature_store_written"])
        self.assertFalse(result.manifest["training_invoked"])
        self.assertFalse(result.manifest["backtest_invoked"])
        self.assertFalse(result.manifest["customer_prediction_generated"])

    def test_provider_registry_includes_akshare_news_provider(self) -> None:
        registry = build_provider_registry()

        self.assertIn("akshare_news", registry)
        self.assertEqual(registry["akshare_news"].data_kind, "news")


if __name__ == "__main__":
    unittest.main()
