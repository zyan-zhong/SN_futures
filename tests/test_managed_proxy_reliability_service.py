from __future__ import annotations

import json
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_data_proxy_service import MANAGED_REQUIRED_RESEARCH_FIELDS
from sn_futures.services.managed_proxy_reliability_service import (
    build_reliability_report,
    compute_endpoint_latency_summary,
    detect_cache_staleness,
    detect_response_size_violation,
    detect_schema_drift_against_baseline,
    run_managed_proxy_canary_check,
)


REQUIRED_CANARY_FIELDS = [
    "source_timestamp",
    "asof_date",
    "ingest_timestamp",
    "feature_date",
    "prediction_cutoff_date",
    *MANAGED_REQUIRED_RESEARCH_FIELDS,
]


class FakeCanaryClient:
    def __init__(
        self,
        *,
        status_code: int = 200,
        content_type: str = "application/json",
        body: dict | None = None,
        elapsed_ms: int = 25,
        raises: Exception | None = None,
    ) -> None:
        self.status_code = status_code
        self.content_type = content_type
        self.body = body if body is not None else {"status": "ok", "fields": list(REQUIRED_CANARY_FIELDS)}
        self.elapsed_ms = elapsed_ms
        self.raises = raises
        self.paths: list[str] = []

    def get_canary(self, path: str, headers: dict[str, str]) -> dict:
        self.paths.append(path)
        if self.raises:
            raise self.raises
        return {
            "status_code": self.status_code,
            "content_type": self.content_type,
            "body": self.body,
            "elapsed_ms": self.elapsed_ms,
        }


class ManagedProxyReliabilityServiceTest(unittest.TestCase):
    def _env(self, tmp: str, **values: str) -> patch:
        base = {
            "SN_DATA_DIR": tmp,
            "SN_INSIGHT_DATA_DIR": "",
            "SN_MANAGED_DATA_PROXY_TOKEN": "",
            "SN_MANAGED_DATA_PROXY_URL": "",
            "SN_MANAGED_DATA_PROXY_ENABLED": "",
            "SN_MANAGED_PROXY_TOKEN": "",
            "SN_MANAGED_PROXY_BASE_URL": "",
            "SN_MANAGED_PROXY_ENABLED": "",
        }
        base.update(values)
        return patch.dict(os.environ, base, clear=False)

    def _configured_env(self, tmp: str) -> patch:
        return self._env(
            tmp,
            SN_MANAGED_PROXY_ENABLED="true",
            SN_MANAGED_PROXY_BASE_URL="https://managed.example",
            SN_MANAGED_PROXY_TOKEN="managed-secret-token",
        )

    def test_unconfigured_endpoint_is_blocked_and_canary_not_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._env(tmp):
            report = run_managed_proxy_canary_check()

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["canary_status"], "not_run")
        self.assertIn("managed_proxy_disabled", report["blocking_reasons"])
        self.assertEqual(report["circuit_breaker_status"], "closed")
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_timeout_fails_and_is_sanitized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._configured_env(tmp):
            report = run_managed_proxy_canary_check(client=FakeCanaryClient(raises=TimeoutError("timeout token=managed-secret-token")))

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["canary_status"], "timeout")
        self.assertEqual(report["timeout_count"], 1)
        self.assertIn("managed_proxy_canary_timeout", report["blocking_reasons"])
        self.assertNotIn("managed-secret-token", serialized)

    def test_5xx_fails_reliability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._configured_env(tmp):
            report = run_managed_proxy_canary_check(client=FakeCanaryClient(status_code=503))

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["canary_status"], "server_error")
        self.assertIn("managed_proxy_canary_5xx", report["blocking_reasons"])

    def test_response_too_large_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._configured_env(tmp):
            large = {"status": "ok", "fields": list(REQUIRED_CANARY_FIELDS), "padding": "x" * 4096}
            report = run_managed_proxy_canary_check(client=FakeCanaryClient(body=large), max_response_bytes=128)

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["canary_status"], "response_too_large")
        self.assertTrue(report["response_size_bytes"] > report["max_response_bytes"])
        self.assertIn("managed_proxy_response_too_large", report["blocking_reasons"])

    def test_invalid_content_type_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._configured_env(tmp):
            report = run_managed_proxy_canary_check(client=FakeCanaryClient(content_type="text/html"))

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["canary_status"], "invalid_content_type")
        self.assertIn("managed_proxy_invalid_content_type", report["blocking_reasons"])

    def test_repeated_failures_open_circuit_breaker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._configured_env(tmp):
            for _ in range(3):
                report = run_managed_proxy_canary_check(client=FakeCanaryClient(raises=TimeoutError("timeout")))

        self.assertEqual(report["circuit_breaker_status"], "open")
        self.assertIn("managed_proxy_circuit_breaker_open", report["blocking_reasons"])
        self.assertEqual(report["next_allowed_action"], "fix_managed_proxy_reliability")

    def test_cached_data_staleness_warns_or_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._configured_env(tmp):
            status_path = Path(tmp) / "outputs" / "fundamentals" / "managed_proxy_status.json"
            status_path.parent.mkdir(parents=True, exist_ok=True)
            status_path.write_text(
                json.dumps(
                    {
                        "status": "using_cache",
                        "from_cache": True,
                        "last_success_time": (datetime.now() - timedelta(days=10)).isoformat(timespec="seconds"),
                    }
                ),
                encoding="utf-8",
            )

            report = run_managed_proxy_canary_check(client=FakeCanaryClient(), cache_max_age_hours=24)

        self.assertIn(report["cache_staleness_status"], {"warning", "fail"})
        self.assertIn("managed_proxy_cache_stale", report["warning_reasons"] + report["blocking_reasons"])

    def test_schema_drift_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._configured_env(tmp):
            report = run_managed_proxy_canary_check(client=FakeCanaryClient(body={"status": "ok", "fields": ["spot_price"]}))

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["schema_drift_status"], "fail")
        self.assertIn("managed_proxy_schema_drift", report["blocking_reasons"])

    def test_canary_success_passes_without_secret_leakage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, self._configured_env(tmp):
            report = run_managed_proxy_canary_check(client=FakeCanaryClient())
            path = Path(report["report_path"])
            text = path.read_text(encoding="utf-8")

        serialized = json.dumps(report, ensure_ascii=False)
        self.assertEqual(report["status"], "pass")
        self.assertEqual(report["canary_status"], "pass")
        self.assertEqual(report["schema_drift_status"], "pass")
        self.assertEqual(report["circuit_breaker_status"], "closed")
        self.assertNotIn("managed-secret-token", serialized)
        self.assertNotIn("managed-secret-token", text)
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_helper_functions_return_stable_statuses(self) -> None:
        self.assertEqual(compute_endpoint_latency_summary([10, 20, 30])["median_ms"], 20)
        self.assertTrue(detect_response_size_violation(200, 100)["violated"])
        self.assertEqual(detect_schema_drift_against_baseline(["spot_price"], ["spot_price", "lme_inventory"])["status"], "fail")
        self.assertEqual(detect_cache_staleness({}, max_age_hours=24)["status"], "not_run")
        self.assertEqual(build_reliability_report(canary_status="pass", blocking_reasons=[])["status"], "pass")


if __name__ == "__main__":
    unittest.main()
