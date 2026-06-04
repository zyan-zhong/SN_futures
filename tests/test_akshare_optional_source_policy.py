from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services import market_data_service as market_svc
from sn_futures.services.provider_status_canonical_service import build_canonical_provider_status


ROOT = Path(__file__).resolve().parents[1]
TMP_ROOT = ROOT / "app_data" / "pytest_tmp"


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


class AkshareOptionalSourcePolicyTest(unittest.TestCase):
    def test_akshare_history_failure_does_not_block_usable_primary_market(self) -> None:
        merged = market_svc.merge_market_data(
            {
                "success": True,
                "quote": {
                    "source": "sina_realtime",
                    "latest_price": 250000,
                    "quote_time": "2026-06-01T10:00:00",
                    "active_contract": "SN0",
                },
                "attempts": [
                    {
                        "provider_name": "sina_realtime",
                        "chain": "realtime",
                        "success": True,
                        "row_count": 1,
                    }
                ],
            },
            {
                "success": False,
                "history": [],
                "attempts": [
                    {
                        "provider_name": "akshare_history",
                        "chain": "history",
                        "success": False,
                        "status_code": "optional_failed",
                        "error_message_zh": "AKShare history optional dependency mini_racer.dll unavailable",
                    }
                ],
                "source": "",
            },
            {},
            {},
        )

        self.assertTrue(merged["success"])
        self.assertEqual(merged["final_status"], "quote_only_partial")
        self.assertEqual(merged["market_status"], "usable")
        self.assertTrue(merged["market_usable"])
        self.assertEqual(merged["blocking_reasons"], [])
        self.assertEqual(merged["optional_source_failures"][0]["provider_name"], "akshare_history")
        self.assertIn("AKShare", json.dumps(merged["warnings_zh"], ensure_ascii=False))

    def test_canonical_status_marks_akshare_optional_failed_and_market_usable(self) -> None:
        TMP_ROOT.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=str(TMP_ROOT)) as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            _write_json(
                output / "market_provider_status.json",
                {
                    "updated_at": "2026-06-01T10:00:00",
                    "final_status": "quote_only_partial",
                    "market_status": "usable",
                    "providers": [
                        {
                            "provider_name": "sina_realtime",
                            "chain": "realtime",
                            "success": True,
                            "row_count": 1,
                            "last_success_time": "2026-06-01T10:00:00",
                        },
                        {
                            "provider_name": "akshare_history",
                            "chain": "history",
                            "success": False,
                            "status_code": "optional_failed",
                            "error_message_zh": (
                                r"Native library dependency not available: "
                                r"C:\Users\Henry Austin\AppData\Local\Temp\_MEI12345\mini_racer.dll"
                            ),
                        },
                    ],
                },
            )

            canonical = build_canonical_provider_status()

        market = canonical["providers"]["market"]
        akshare = canonical["providers"]["akshare_history"]
        self.assertEqual(market["status"], "usable")
        self.assertTrue(market["success"])
        self.assertEqual(akshare["status"], "optional_failed")
        self.assertEqual(akshare["severity"], "optional_failed")
        self.assertTrue(akshare["optional"])
        self.assertFalse(akshare["blocks_market"])
        self.assertIn("\u53ef\u9009\u6e90\u5931\u8d25\uff0c\u4e0d\u5f71\u54cd\u4e3b\u884c\u60c5", akshare["message_zh"])
        self.assertIn("mini_racer.dll", akshare["message_zh"])
        self.assertNotIn(r"C:\Users", akshare["message_zh"])


if __name__ == "__main__":
    unittest.main()
