from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures import v2_api
from sn_futures.services.feature_store_service import build_feature_store
from sn_futures.services.provenance_gate_service import build_watermark_record, evaluate_provenance_gate
from sn_futures.services.terminal_service import build_terminal_data_status


class ProvenanceGateContractTest(unittest.TestCase):
    def test_missing_daily_bars_blocks_prediction_and_backtest(self) -> None:
        gate = evaluate_provenance_gate([], purpose="prediction")

        self.assertFalse(gate["allowed"])
        self.assertFalse(gate["allowed_for_prediction"])
        self.assertFalse(gate["allowed_for_backtest"])
        self.assertIn("缺少 daily_bar", " ".join(gate["blocking_reasons"]))

    def test_stale_last_good_cache_is_display_only(self) -> None:
        record = build_watermark_record(
            data_kind="daily_bar",
            provider="local_cache",
            row_count=120,
            cache_status="last_good_cache",
            stale_status="stale",
            as_of="2026-05-01",
            trading_date="2026-05-01",
        )

        display_gate = evaluate_provenance_gate([record], purpose="display")
        prediction_gate = evaluate_provenance_gate([record], purpose="prediction")

        self.assertTrue(display_gate["allowed"])
        self.assertTrue(display_gate["allowed_for_display"])
        self.assertFalse(prediction_gate["allowed"])
        self.assertFalse(prediction_gate["allowed_for_prediction"])
        self.assertIn("stale", " ".join(prediction_gate["blocking_reasons"]))

    def test_sample_data_blocks_training_prediction_and_backtest(self) -> None:
        record = build_watermark_record(
            data_kind="daily_bar",
            provider="unit_test",
            row_count=200,
            cache_status="remote",
            stale_status="fresh",
            sample_data_used=True,
            as_of="2026-06-01",
            trading_date="2026-06-01",
        )

        for purpose in ("training", "prediction", "backtest"):
            gate = evaluate_provenance_gate([record], purpose=purpose)
            self.assertFalse(gate["allowed"], purpose)
            self.assertIn("sample_data_used", " ".join(gate["blocking_reasons"]))

    def test_realtime_quote_only_is_latest_display_not_backtest(self) -> None:
        quote = build_watermark_record(
            data_kind="realtime_quote",
            provider="sina",
            row_count=1,
            cache_status="remote",
            stale_status="fresh",
            fetched_at="2026-06-01T10:00:00+08:00",
        )

        display_gate = evaluate_provenance_gate([quote], purpose="display")
        backtest_gate = evaluate_provenance_gate([quote], purpose="backtest")

        self.assertTrue(display_gate["allowed"])
        self.assertTrue(display_gate["display_latest_only"])
        self.assertFalse(backtest_gate["allowed"])
        self.assertIn("缺少 daily_bar", " ".join(backtest_gate["blocking_reasons"]))

    def test_news_without_source_published_at_cannot_be_high_weight_event_factor(self) -> None:
        news = build_watermark_record(
            data_kind="news",
            provider="newsapi",
            row_count=3,
            cache_status="remote",
            stale_status="fresh",
            source_published_at="",
        )

        gate = evaluate_provenance_gate([news], purpose="high_weight_event_factor")

        self.assertFalse(gate["allowed"])
        self.assertFalse(gate["allowed_for_high_weight_event_factor"])
        self.assertIn("source_published_at", " ".join(gate["blocking_reasons"]))

    def test_prediction_api_blocks_when_runtime_root_has_no_daily_bars(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            payload = v2_api.run_predict_api(horizon="tomorrow")

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["provenance_gate"]["allowed_for_prediction"])
        self.assertIn("缺少 daily_bar", " ".join(payload["blocking_reasons"]))

    def test_backtest_diagnostics_blocks_when_only_realtime_quote_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            out.mkdir(parents=True, exist_ok=True)
            (out / "sn_live_snapshot.json").write_text(
                json.dumps(
                    {
                        "generated_at": "2026-06-01T10:00:00+08:00",
                        "quotes": [{"symbol": "SN0", "latest": 250000}],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            payload = v2_api.get_backtest_diagnostics("tomorrow")

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["provenance_gate"]["allowed_for_backtest"])
        self.assertIn("缺少 daily_bar", " ".join(payload["blocking_reasons"]))

    def test_feature_store_build_uses_gate_before_constructing_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            out = Path(tmp) / "outputs"
            out.mkdir(parents=True, exist_ok=True)
            record = build_watermark_record(
                data_kind="daily_bar",
                provider="unit_test",
                row_count=120,
                cache_status="remote",
                stale_status="fresh",
                sample_data_used=True,
                as_of="2026-06-01",
                trading_date="2026-06-01",
            )
            (out / "data_watermark.json").write_text(
                json.dumps({"provenance_records": [record]}, ensure_ascii=False),
                encoding="utf-8",
            )
            payload = build_feature_store(version="v3")

        self.assertEqual(payload["status"], "blocked")
        self.assertFalse(payload["provenance_gate"]["allowed_for_feature_store"])
        self.assertIn("sample_data_used", " ".join(payload["blocking_reasons"]))

    def test_terminal_data_status_exposes_provenance_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            payload = build_terminal_data_status()

        self.assertIn("provenance_gate", payload["data_watermark"])
        self.assertFalse(payload["data_watermark"]["provenance_gate"]["allowed_for_prediction"])


if __name__ == "__main__":
    unittest.main()
