from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.real_data_coverage_validation_service import build_real_data_coverage_validation


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_market_history(output_dir: Path, rows: int = 140) -> list[str]:
    start = date(2026, 1, 1)
    dates = [(start + timedelta(days=idx)).isoformat() for idx in range(rows)]
    history = []
    for idx, day in enumerate(dates):
        close = 250000 + idx * 5
        history.append({"trade_date": day, "open": close - 30, "high": close + 80, "low": close - 90, "close": close, "volume": 1000 + idx})
    _write_json(output_dir / "sn_market_history.json", {"sample": False, "history": history})
    return dates


class FakeManagedClient:
    def __init__(self, dates: list[str]) -> None:
        self.dates = dates

    def get_json(self, path: str, headers: dict[str, str]) -> dict[str, object]:
        self.last_path = path
        self.last_headers = headers
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


class RealManagedProxyOrDisabledFlowTest(unittest.TestCase):
    def test_disabled_managed_proxy_blocks_without_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_TUSHARE_TOKEN": "",
                "SN_MANAGED_DATA_PROXY_TOKEN": "",
                "SN_MANAGED_DATA_PROXY_URL": "",
                "SN_MANAGED_DATA_PROXY_ENABLED": "",
            },
            clear=False,
        ):
            output_dir = Path(tmp) / "outputs"
            _write_market_history(output_dir)

            report = build_real_data_coverage_validation(force=False)

            self.assertEqual(report["source_status"]["managed_proxy"]["status"], "disabled")
            self.assertEqual(report["candidate_v6_readiness"]["status"], "blocked")
            self.assertFalse(report["training_invoked"])
            self.assertFalse(report["active_updated"])
            self.assertFalse(report["customer_prediction_generated"])

    def test_configured_managed_proxy_real_rows_raise_institutional_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(
            os.environ,
            {
                "SN_DATA_DIR": tmp,
                "SN_TUSHARE_TOKEN": "",
                "SN_MANAGED_DATA_PROXY_TOKEN": "managed-token",
                "SN_MANAGED_DATA_PROXY_URL": "https://managed.example",
                "SN_MANAGED_DATA_PROXY_ENABLED": "1",
            },
            clear=False,
        ):
            output_dir = Path(tmp) / "outputs"
            dates = _write_market_history(output_dir)

            report = build_real_data_coverage_validation(force=True, managed_client=FakeManagedClient(dates))

            self.assertEqual(report["source_status"]["managed_proxy"]["status"], "success")
            self.assertGreater(report["source_status"]["managed_proxy"]["row_count"], 0)
            self.assertGreater(report["feature_coverage_delta"]["basis"]["after"], report["feature_coverage_delta"]["basis"]["before"])
            self.assertGreater(report["feature_coverage_delta"]["inventory"]["after"], report["feature_coverage_delta"]["inventory"]["before"])
            self.assertGreater(report["feature_coverage_delta"]["term_structure"]["after"], report["feature_coverage_delta"]["term_structure"]["before"])
            self.assertIn("spot_futures_basis", report["candidate_v6_readiness"]["new_fields"])
            self.assertIn(report["candidate_v6_readiness"]["status"], {"ready", "blocked"})
            self.assertFalse(report["training_invoked"])
            self.assertFalse(report["active_updated"])
            self.assertFalse(report["customer_prediction_generated"])
            self.assertFalse((output_dir / "model_registry" / "active_model.json").exists())
            self.assertFalse((output_dir / "sn_live_predictions.json").exists())


if __name__ == "__main__":
    unittest.main()
