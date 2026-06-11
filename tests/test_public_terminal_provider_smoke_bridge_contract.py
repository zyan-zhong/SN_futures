from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


sys.path.insert(0, "src")

from sn_futures.api.terminal_api import handle_terminal_api  # noqa: E402
from sn_futures.public_terminal.provider_smoke_result_bridge_service import (  # noqa: E402
    bridge_provider_smoke_result,
    get_public_provider_smoke_report,
)
from sn_futures.public_terminal.readiness_service import build_public_terminal_readiness  # noqa: E402
from sn_futures.public_terminal.refresh_orchestrator import run_public_refresh_data_status  # noqa: E402


DOWNSTREAM_FLAGS = (
    "training_invoked",
    "prediction_generated",
    "backtest_invoked",
    "feature_store_written",
    "production_cache_written",
    "customer_prediction_generated",
)


def fake_success(provider_id: str, row_count: int = 3) -> dict[str, object]:
    return {
        "provider_id": provider_id,
        "provider": provider_id,
        "status": "success",
        "success": True,
        "row_count": row_count,
        "source_statuses": [{"provider_id": provider_id, "status": "success", "success": True, "row_count": row_count}],
        "manifest": {
            "provider_id": provider_id,
            "row_count": row_count,
            "source_statuses": [{"provider_id": provider_id, "success": True, "row_count": row_count}],
            "sample_data_used": False,
            "baseline_used": False,
            "training_invoked": False,
            "prediction_generated": False,
            "backtest_invoked": False,
        },
    }


def fake_blocked(provider_id: str, error_code: str) -> dict[str, object]:
    return {
        "provider_id": provider_id,
        "provider": provider_id,
        "status": "blocked",
        "success": False,
        "error_code": error_code,
        "row_count": 0,
        "source_statuses": [{"provider_id": provider_id, "status": "blocked", "success": False, "error_code": error_code}],
        "manifest": {
            "provider_id": provider_id,
            "row_count": 0,
            "blocking_reasons": [error_code],
            "source_statuses": [{"provider_id": provider_id, "success": False, "error_code": error_code}],
            "training_invoked": False,
            "prediction_generated": False,
            "backtest_invoked": False,
        },
    }


def fake_legacy_provider_test_success(provider_id: str, row_count: int = 3) -> dict[str, object]:
    return {
        "success": True,
        "provider": provider_id,
        "request_params_sanitized": {"provider": provider_id},
        "status": {
            "status": "success",
            "row_count": row_count,
            "source_statuses": [
                {"provider_id": provider_id, "status": "success", "success": True, "row_count": row_count}
            ],
        },
    }


class PublicTerminalProviderSmokeBridgeContractTest(unittest.TestCase):
    def test_alpha_vantage_fake_success_unlocks_readiness_provider_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            bridge_provider_smoke_result(fake_success("alpha_vantage", row_count=5), source="legacy_provider_test")
            readiness = build_public_terminal_readiness()

        self.assertTrue(readiness["provider_smoke_passed"])
        self.assertTrue(readiness["ready_for_refresh"])
        self.assertEqual(readiness["next_action"], "refresh_data_status")

    def test_newsapi_fake_success_unlocks_readiness_provider_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            bridge_provider_smoke_result(fake_success("newsapi", row_count=4), source="legacy_provider_test")
            readiness = build_public_terminal_readiness()

        self.assertTrue(readiness["provider_smoke_passed"])
        self.assertEqual(readiness["provider_status"]["passed_providers"], ["newsapi"])

    def test_akshare_fake_success_unlocks_readiness_provider_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            bridge_provider_smoke_result(fake_success("akshare_news", row_count=50), source="provider_only_harness")
            report = get_public_provider_smoke_report()
            readiness = build_public_terminal_readiness()

        self.assertEqual(report["passed_count"], 1)
        self.assertTrue(readiness["provider_smoke_passed"])
        self.assertEqual(readiness["provider_status"]["source_statuses"][0]["row_count"], 50)

    def test_legacy_provider_test_result_shape_bridges_nested_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            bridge_provider_smoke_result(fake_legacy_provider_test_success("alpha_vantage", row_count=8), source="legacy_provider_test")
            readiness = build_public_terminal_readiness()

        self.assertTrue(readiness["provider_smoke_passed"])
        self.assertEqual(readiness["provider_status"]["source_statuses"][0]["provider_id"], "alpha_vantage")
        self.assertEqual(readiness["provider_status"]["source_statuses"][0]["row_count"], 8)

    def test_legacy_terminal_provider_test_endpoint_writes_public_smoke_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True), patch(
            "sn_futures.api.terminal_api.test_provider",
            return_value=fake_legacy_provider_test_success("newsapi", row_count=6),
        ):
            status, payload = handle_terminal_api(
                "/api/terminal/providers/test",
                method="POST",
                body={"provider": "newsapi"},
            )
            readiness = build_public_terminal_readiness()

        self.assertEqual(status, 200)
        self.assertTrue(payload["success"])
        self.assertTrue(readiness["provider_smoke_passed"])
        self.assertEqual(readiness["provider_status"]["passed_providers"], ["newsapi"])

    def test_public_readiness_endpoint_consumes_unified_smoke_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            bridge_provider_smoke_result(fake_success("alpha_vantage", row_count=5), source="legacy_provider_test")
            status, payload = handle_terminal_api("/api/public-terminal/readiness", method="GET")

        self.assertEqual(status, 200)
        self.assertTrue(payload["provider_smoke_passed"])
        self.assertEqual(payload["next_action"], "refresh_data_status")

    def test_tushare_key_invalid_blocks_readiness_with_visible_reason(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            bridge_provider_smoke_result(fake_blocked("tushare_futures", "key_invalid"), source="provider_only_harness")
            readiness = build_public_terminal_readiness()

        self.assertFalse(readiness["provider_smoke_passed"])
        self.assertEqual(readiness["next_action"], "run_provider_smoke")
        self.assertIn("key_invalid", readiness["blocking_reasons"])
        self.assertEqual(readiness["provider_status"]["source_statuses"][0]["error_code"], "key_invalid")

    def test_shfe_api_changed_is_blocked_but_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            bridge_provider_smoke_result(fake_blocked("shfe_public", "api_changed"), source="provider_only_harness")
            readiness = build_public_terminal_readiness()

        self.assertFalse(readiness["provider_smoke_passed"])
        self.assertIn("api_changed", readiness["blocking_reasons"])
        self.assertEqual(readiness["provider_status"]["source_statuses"][0]["provider_id"], "shfe_public")

    def test_public_policy_rss_api_changed_is_blocked_but_visible(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            bridge_provider_smoke_result(fake_blocked("public_policy_rss", "api_changed"), source="provider_only_harness")
            readiness = build_public_terminal_readiness()

        self.assertFalse(readiness["provider_smoke_passed"])
        self.assertIn("api_changed", readiness["blocking_reasons"])
        self.assertEqual(readiness["provider_status"]["source_statuses"][0]["provider_id"], "public_policy_rss")

    def test_refresh_proceeds_when_required_market_provider_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            bridge_provider_smoke_result(fake_success("alpha_vantage", row_count=7), source="legacy_provider_test")
            refresh = run_public_refresh_data_status()
            watermark_path = Path(tmp) / "outputs" / "public_terminal" / "data_watermark.json"
            watermark_exists = watermark_path.exists()

        self.assertEqual(refresh["status"], "success")
        self.assertTrue(refresh["result"]["data_watermark_updated"])
        self.assertTrue(watermark_exists)
        for flag in DOWNSTREAM_FLAGS:
            self.assertFalse(refresh.get(flag), flag)

    def test_public_refresh_endpoint_uses_unified_smoke_report_and_exposes_pollable_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            bridge_provider_smoke_result(fake_success("alpha_vantage", row_count=7), source="legacy_provider_test")
            start_status, task = handle_terminal_api("/api/public-terminal/refresh-data-status", method="POST")
            poll_status, completed = handle_terminal_api(f"/api/public-terminal/tasks/{task.get('task_id')}", method="GET")
            watermark_path = Path(tmp) / "outputs" / "public_terminal" / "data_watermark.json"
            watermark_exists = watermark_path.exists()

        self.assertEqual(start_status, 200)
        self.assertIn(task["status"], {"queued", "running", "success"})
        self.assertEqual(poll_status, 200)
        self.assertEqual(completed["status"], "success")
        self.assertTrue(completed["result"]["data_watermark_updated"])
        self.assertTrue(watermark_exists)
        for flag in DOWNSTREAM_FLAGS:
            self.assertFalse(completed.get(flag), flag)

    def test_refresh_blocks_when_no_provider_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            bridge_provider_smoke_result(fake_blocked("local_api_provider", "not_configured"), source="provider_only_harness")
            refresh = run_public_refresh_data_status()
            watermark_path = Path(tmp) / "outputs" / "public_terminal" / "data_watermark.json"
            watermark_exists = watermark_path.exists()

        self.assertEqual(refresh["status"], "blocked")
        self.assertEqual(refresh["reason"], "no_active_provider_smoke_pass")
        self.assertFalse(watermark_exists)
        for flag in DOWNSTREAM_FLAGS:
            self.assertFalse(refresh.get(flag), flag)

    def test_bridge_does_not_write_downstream_artifacts_or_flags(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=True):
            report = bridge_provider_smoke_result(fake_success("newsapi", row_count=2), source="legacy_provider_test")
            runtime = Path(tmp)

            forbidden_paths = [
                runtime / "outputs" / "feature_store",
                runtime / "outputs" / "predictions",
                runtime / "outputs" / "backtest",
                runtime / "outputs" / "models",
            ]
            serialized = json.dumps(report, ensure_ascii=False)

        for flag in DOWNSTREAM_FLAGS:
            self.assertFalse(report.get(flag), flag)
            self.assertIn(f'"{flag}": false', serialized)
        for path in forbidden_paths:
            self.assertFalse(path.exists(), str(path))


if __name__ == "__main__":
    unittest.main()
