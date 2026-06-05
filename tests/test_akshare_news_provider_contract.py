from __future__ import annotations

import importlib
import json
import sys
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


class SecretLeakingAkShareNews:
    def futures_news_shmet(self, symbol: str) -> pd.DataFrame:
        raise RuntimeError("Authorization Bearer secret-akshare-token path C:/Users/Henry/secrets.json")

    def stock_info_global_cls(self, symbol: str) -> pd.DataFrame:
        return pd.DataFrame()


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
