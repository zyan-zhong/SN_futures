from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.provider_result_bridge_service import (  # noqa: E402
    bridge_public_policy_rss_service_output,
    bridge_shfe_public_service_output,
    bridge_tushare_service_output,
)
from sn_futures.services.provider_status_canonical_service import build_canonical_provider_status  # noqa: E402
from sn_futures.services.terminal_service import build_terminal_data_status  # noqa: E402


SECRET = "TUSHARE_SECRET_TOKEN_1234567890"


def _assert_no_downstream_writes(payload: dict[str, object]) -> None:
    manifest = payload["manifest"]
    assert isinstance(manifest, dict)
    for key in (
        "feature_store_written",
        "training_invoked",
        "backtest_invoked",
        "active_updated",
        "customer_prediction_generated",
        "sample_data_used",
        "baseline_used",
    ):
        assert manifest[key] is False


class InstitutionalServiceProviderBridgeTest(unittest.TestCase):
    def test_tushare_service_success_maps_to_provider_result_manifest(self) -> None:
        result = bridge_tushare_service_output(
            {
                "generated_at": "2026-06-07T09:30:00",
                "status": "success",
                "success": True,
                "rows": [{"ts_code": "SN2601.SHFE", "trade_date": "2026-06-01", "close": 200000}],
                "results": {
                    "tushare_daily": {"success": True, "status": "success", "row_count": 1},
                },
            }
        )
        payload = result.to_dict()

        self.assertTrue(result.success)
        self.assertEqual(result.provider_id, "tushare_futures")
        self.assertEqual(result.data_kind, "futures_fundamentals")
        self.assertGreater(result.manifest["row_count"], 0)
        self.assertEqual(result.manifest["source_statuses"][0]["source_id"], "tushare_daily")
        self.assertFalse(result.manifest["safe_refresh_available"])
        _assert_no_downstream_writes(payload)

    def test_tushare_token_missing_blocks_without_secret_leak(self) -> None:
        result = bridge_tushare_service_output(
            {
                "status": "token_missing",
                "success": False,
                "rows": [],
                "error_message_zh": f"token missing: {SECRET}",
            },
            secrets=(SECRET,),
        )
        serialized = json.dumps(result.to_dict(), ensure_ascii=False)

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "token_missing")
        self.assertEqual(result.rows, [])
        self.assertEqual(result.normalized_rows, [])
        self.assertFalse(result.manifest["safe_refresh_available"])
        self.assertNotIn(SECRET, serialized)
        self.assertIn("***", serialized)
        _assert_no_downstream_writes(result.to_dict())

    def test_tushare_rate_limit_is_structured(self) -> None:
        result = bridge_tushare_service_output(
            {
                "status": "rate_limited",
                "success": False,
                "rows": [],
                "message_zh": "rate limit reached",
            }
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "rate_limited")
        self.assertTrue(result.rate_limited)
        self.assertIn("rate_limited", result.manifest["blocking_reasons"])

    def test_shfe_public_service_success_maps_nested_results_and_hash(self) -> None:
        result = bridge_shfe_public_service_output(
            {
                "generated_at": "2026-06-07T10:00:00",
                "status": "success",
                "success": True,
                "results": {
                    "shfe_inventory": {
                        "success": True,
                        "status": "success",
                        "row_count": 1,
                        "rows": [{"symbol": "SN", "trade_date": "2026-06-01", "inventory": 1200}],
                    },
                    "shfe_warehouse_receipts": {
                        "success": False,
                        "status": "no_tin_rows",
                        "row_count": 0,
                    },
                },
            }
        )

        self.assertTrue(result.success)
        self.assertEqual(result.provider_id, "shfe_public")
        self.assertEqual(result.data_kind, "exchange_public")
        self.assertEqual(result.manifest["row_count"], 1)
        self.assertTrue(result.manifest["content_hash"])
        self.assertGreaterEqual(len(result.manifest["source_statuses"]), 2)
        _assert_no_downstream_writes(result.to_dict())

    def test_shfe_waf_or_network_block_is_structured_without_downstream_writes(self) -> None:
        result = bridge_shfe_public_service_output(
            {
                "status": "blocked_by_waf",
                "success": False,
                "results": {
                    "shfe_direct_probe": {
                        "success": False,
                        "status": "blocked_by_waf",
                        "error_message_zh": "captcha waf blocked",
                    }
                },
            }
        )

        self.assertFalse(result.success)
        self.assertIn(result.error_code, {"waf_blocked", "request_failed"})
        self.assertEqual(result.normalized_rows, [])
        _assert_no_downstream_writes(result.to_dict())

    def test_public_policy_rss_events_keep_published_time_separate_and_demote_missing_time(self) -> None:
        result = bridge_public_policy_rss_service_output(
            {
                "status": "success",
                "success": True,
                "generated_at": "2026-06-07T12:00:00",
                "events": [
                    {
                        "title": "MIIT tin solder policy update",
                        "url": "https://www.miit.gov.cn/policy/tin",
                        "source": "MIIT",
                        "source_published_at": "2026-06-01T09:00:00+08:00",
                        "fetched_at": "2026-06-07T12:00:00",
                        "used_in_model": True,
                    },
                    {
                        "title": "Old policy page without published time",
                        "url": "https://www.ndrc.gov.cn/policy/old",
                        "source": "NDRC",
                        "fetched_at": "2026-06-07T12:00:00",
                        "used_in_model": True,
                    },
                ],
            }
        )

        self.assertTrue(result.success)
        self.assertEqual(result.provider_id, "public_policy_rss")
        self.assertEqual(result.data_kind, "policy")
        self.assertEqual(result.normalized_rows[0]["source_published_at"], "2026-06-01T09:00:00+08:00")
        self.assertNotEqual(result.fetched_at, result.source_timestamp)
        self.assertFalse(result.normalized_rows[1]["used_in_model"])
        self.assertEqual(result.normalized_rows[1]["rejection_reason"], "missing_source_published_at")
        self.assertEqual(result.manifest["source_published_at_coverage"], 0.5)

    def test_malformed_rows_block_with_no_normalized_rows(self) -> None:
        result = bridge_tushare_service_output(
            {
                "status": "success",
                "success": True,
                "rows": [{"ts_code": "SN2601.SHFE"}],
            }
        )

        self.assertFalse(result.success)
        self.assertEqual(result.error_code, "missing_required_columns")
        self.assertEqual(result.normalized_rows, [])

    def test_canonical_status_and_terminal_data_status_read_bridge_provider_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            result = bridge_tushare_service_output(
                {
                    "generated_at": "2026-06-07T09:30:00",
                    "status": "success",
                    "success": True,
                    "rows": [{"ts_code": "SN2601.SHFE", "trade_date": "2026-06-01", "close": 200000}],
                },
                persist=True,
            )
            canonical = build_canonical_provider_status()
            data_status = build_terminal_data_status()

        self.assertTrue(result.success)
        tushare = canonical["providers"]["tushare"]
        self.assertEqual(tushare["status"], "success")
        self.assertEqual(tushare["provider_status_source"], "provider_result_bridge")
        self.assertIn("provider_results", tushare["source_file"])
        sources = data_status.get("sources", [])
        self.assertTrue(any(source.get("provider_id") == "tushare" and source.get("row_count") == 1 for source in sources))


if __name__ == "__main__":
    unittest.main()
