from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.provider_only_smoke_harness import run_provider_only_smoke, with_temp_runtime  # noqa: E402


SECRET = "LOCAL_PROVIDER_TOKEN_1234567890"


@dataclass
class FakeHttpResponse:
    status_code: int
    payload: object


class FakeLocalHttpClient:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def get_json(self, url: str, *, headers: dict[str, str], timeout_seconds: int) -> FakeHttpResponse:
        self.calls.append({"url": url, "headers": headers, "timeout_seconds": timeout_seconds})
        return FakeHttpResponse(
            200,
            {
                "rows": [
                    {
                        "symbol": "SN",
                        "open": 200000,
                        "high": 201000,
                        "low": 199000,
                        "close": 200500,
                        "source_timestamp": "2026-06-07T09:00:00",
                    }
                ]
            },
        )


class TimeoutLocalHttpClient:
    def get_json(self, url: str, *, headers: dict[str, str], timeout_seconds: int) -> FakeHttpResponse:
        del url, headers, timeout_seconds
        raise TimeoutError("provider timed out")


class FakeAkShareNews:
    def futures_news_shmet(self, symbol: str):  # type: ignore[no-untyped-def]
        import pandas as pd

        return pd.DataFrame(
            [
                {
                    "title": "SHFE tin warehouse warrants tighten",
                    "content": "SHFE tin and LME tin inventory news for smoke.",
                    "source_published_at": "2026-06-07T09:00:00+08:00",
                }
            ]
        )

    def stock_info_global_cls(self, symbol: str):  # type: ignore[no-untyped-def]
        import pandas as pd

        return pd.DataFrame()


class FakeRowsClient:
    def __init__(self, rows: list[dict[str, object]] | None = None, error: Exception | None = None) -> None:
        self.rows = rows or []
        self.error = error
        self.called = False

    def fetch_rows(self) -> list[dict[str, object]]:
        self.called = True
        if self.error:
            raise self.error
        return self.rows


class ProviderOnlySmokeHarnessTest(unittest.TestCase):
    def test_default_no_remote_blocks_without_fake_clients_and_marks_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_provider_only_smoke(
                providers=["akshare_news", "tushare_futures", "shfe_public", "public_policy_rss", "local_api_provider"],
                runtime_dir=Path(tmp),
            )

        self.assertFalse(report["allow_remote"])
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(len(report["providers"]), 5)
        for item in report["providers"]:
            self.assertFalse(item["manifest"]["allow_remote"])
            self.assertFalse(item["manifest"]["feature_store_written"])
            self.assertFalse(item["manifest"]["training_invoked"])
            self.assertFalse(item["manifest"]["backtest_invoked"])
            self.assertFalse(item["manifest"]["customer_prediction_generated"])
            self.assertIn("source_statuses", item["manifest"])

    def test_temp_runtime_sets_env_and_does_not_use_repo_outputs(self) -> None:
        repo_root = Path.cwd()
        with with_temp_runtime() as runtime:
            self.assertEqual(os.environ["SN_DATA_DIR"], str(runtime))
            self.assertEqual(os.environ["SN_INSIGHT_DATA_DIR"], str(runtime))
            self.assertEqual(os.environ["SN_DISABLE_AUTO_SCHEDULER"], "1")
            self.assertNotEqual((repo_root / "outputs").resolve(), (runtime / "outputs").resolve())
            (runtime / "outputs").mkdir(parents=True, exist_ok=True)
            self.assertTrue((runtime / "outputs").exists())

    def test_aggregate_continues_when_one_provider_fails(self) -> None:
        local_client = FakeLocalHttpClient()
        shfe_client = FakeRowsClient([{"symbol": "SN", "trade_date": "2026-06-07", "inventory": 1200}])
        tushare_client = FakeRowsClient(error=RuntimeError("429 rate limit"))

        with tempfile.TemporaryDirectory() as tmp:
            report = run_provider_only_smoke(
                providers=["local_api_provider", "shfe_public", "tushare_futures"],
                runtime_dir=Path(tmp),
                fake_clients={
                    "local_api_provider": local_client,
                    "shfe_public": shfe_client,
                    "tushare_futures": tushare_client,
                },
            )

        statuses = {item["provider_id"]: item for item in report["providers"]}
        self.assertEqual(report["provider_count"], 3)
        self.assertEqual(statuses["local_api_provider"]["status"], "pass")
        self.assertEqual(statuses["shfe_public"]["status"], "pass")
        self.assertEqual(statuses["tushare_futures"]["error_code"], "rate_limited")
        self.assertEqual(report["failed_count"], 1)
        self.assertGreaterEqual(report["passed_count"], 2)

    def test_downstream_flags_are_false_for_success_and_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_provider_only_smoke(
                providers=["local_api_provider", "tushare_futures"],
                runtime_dir=Path(tmp),
                fake_clients={
                    "local_api_provider": FakeLocalHttpClient(),
                    "tushare_futures": FakeRowsClient(error=TimeoutError("timeout")),
                },
            )

        for item in report["providers"]:
            manifest = item["manifest"]
            for key in (
                "feature_store_written",
                "training_invoked",
                "backtest_invoked",
                "customer_prediction_generated",
                "prediction_generated",
                "production_cache_written",
            ):
                self.assertFalse(manifest[key], f"{item['provider_id']} {key}")

    def test_timeout_is_structured_and_aggregate_continues(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_provider_only_smoke(
                providers=["local_api_provider", "shfe_public"],
                runtime_dir=Path(tmp),
                fake_clients={
                    "local_api_provider": TimeoutLocalHttpClient(),
                    "shfe_public": FakeRowsClient([{"symbol": "SN", "trade_date": "2026-06-07"}]),
                },
            )

        statuses = {item["provider_id"]: item for item in report["providers"]}
        self.assertEqual(statuses["local_api_provider"]["error_code"], "request_timeout")
        self.assertTrue(statuses["local_api_provider"]["manifest"]["source_statuses"][0]["timed_out"])
        self.assertEqual(statuses["shfe_public"]["status"], "pass")

    def test_explicit_allow_remote_flag_is_visible_but_fake_client_still_controls_call(self) -> None:
        local_client = FakeLocalHttpClient()
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_LOCAL_API_PROVIDER_BASE_URL": "https://local-provider.example",
                "SN_LOCAL_API_PROVIDER_TOKEN": SECRET,
            },
            clear=False,
        ):
            report = run_provider_only_smoke(
                providers=["local_api_provider"],
                allow_remote=True,
                runtime_dir=Path(tmp),
                fake_clients={"local_api_provider": local_client},
            )

        self.assertTrue(report["allow_remote"])
        self.assertIn("explicit_remote_smoke_enabled", report["warnings"])
        self.assertEqual(len(local_client.calls), 1)
        self.assertEqual(report["providers"][0]["status"], "pass")
        self.assertTrue(report["providers"][0]["manifest"]["allow_remote"])

    def test_optional_persist_writes_report_only_under_temp_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            report = run_provider_only_smoke(
                providers=["local_api_provider"],
                runtime_dir=Path(tmp),
                fake_clients={"local_api_provider": FakeLocalHttpClient()},
                persist=True,
            )
            report_path = Path(str(report["report_path"]))

            self.assertTrue(report_path.exists())
            self.assertTrue(str(report_path).startswith(str(Path(tmp))))
            encoded = report_path.read_text(encoding="utf-8")

        self.assertIn("local_api_provider", encoded)
        self.assertNotIn(SECRET, json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
