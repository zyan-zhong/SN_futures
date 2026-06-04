from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.managed_pit_replay_service import (
    build_pit_replay_report,
    detect_future_row_selected,
    detect_ingest_timestamp_misuse,
    run_pit_replay_harness,
    select_asof_row_for_cutoff,
)


def row(row_id: str, asof: str, source: str, ingest: str = "2026-01-09T12:00:00", **extra: object) -> dict:
    payload = {
        "row_id": row_id,
        "feature_date": "2026-01-10",
        "prediction_cutoff_date": "2026-01-10",
        "asof_date": asof,
        "source_timestamp": source,
        "ingest_timestamp": ingest,
        "spot_price": 210000,
    }
    payload.update(extra)
    return payload


class ManagedPitReplayServiceTest(unittest.TestCase):
    def test_selects_latest_asof_source_before_cutoff_and_rejects_future_rows(self) -> None:
        rows = [
            row("old", "2026-01-07", "2026-01-07T09:00:00"),
            row("latest_valid", "2026-01-09", "2026-01-09T10:00:00", ingest="2026-01-12T12:00:00"),
            row("future_asof", "2026-01-11", "2026-01-09T10:00:00"),
            row("future_source", "2026-01-09", "2026-01-11T10:00:00"),
        ]

        selected = select_asof_row_for_cutoff(rows, "2026-01-10")
        report = build_pit_replay_report(rows=rows, cutoffs=["2026-01-10"], write=False)

        self.assertEqual(selected["row_id"], "latest_valid")
        self.assertFalse(detect_future_row_selected(selected, "2026-01-10"))
        self.assertFalse(detect_ingest_timestamp_misuse(selected))
        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["cases_run"], 1)
        self.assertEqual(report["cases_passed"], 1)
        self.assertEqual(report["cases_failed"], 0)
        self.assertEqual(report["rejected_future_rows"][0]["row_id"], "future_asof")
        self.assertEqual(report["rejected_future_rows"][1]["row_id"], "future_source")
        self.assertTrue(report["point_in_time_join_ready"])
        self.assertFalse(report["training_invoked"])
        self.assertFalse(report["active_updated"])
        self.assertFalse(report["customer_prediction_generated"])

    def test_ingest_after_cutoff_does_not_fail_or_drive_selection(self) -> None:
        rows = [
            row("valid_older", "2026-01-07", "2026-01-07T09:00:00", ingest="2026-01-07T10:00:00"),
            row("valid_latest_with_late_ingest", "2026-01-09", "2026-01-09T09:00:00", ingest="2026-01-20T10:00:00"),
        ]

        report = build_pit_replay_report(rows=rows, cutoffs=["2026-01-10"], write=False)

        self.assertEqual(report["status"], "ready")
        self.assertEqual(report["selected_rows"][0]["row_id"], "valid_latest_with_late_ingest")
        self.assertFalse(report["ingest_timestamp_misuse_detected"])
        self.assertTrue(report["point_in_time_join_ready"])

    def test_source_or_asof_after_cutoff_fail_even_when_fields_exist(self) -> None:
        rows = [
            row("future_source_only", "2026-01-09", "2026-01-11T09:00:00"),
            row("future_asof_only", "2026-01-11", "2026-01-09T09:00:00"),
        ]

        report = build_pit_replay_report(rows=rows, cutoffs=["2026-01-10"], write=False)

        self.assertEqual(report["status"], "blocked")
        self.assertEqual(report["cases_failed"], 1)
        self.assertFalse(report["point_in_time_join_ready"])
        self.assertIn("future_rows_after_cutoff", report["blocking_reasons"])
        self.assertIn("no_valid_asof_row_for_cutoff", report["blocking_reasons"])

    def test_same_asof_tiebreak_is_deterministic(self) -> None:
        rows = [
            row("revision_1", "2026-01-09", "2026-01-09T09:00:00", provider_revision=1),
            row("revision_2", "2026-01-09", "2026-01-09T09:00:00", provider_revision=2),
        ]

        first = select_asof_row_for_cutoff(rows, "2026-01-10")
        second = select_asof_row_for_cutoff(list(reversed(rows)), "2026-01-10")
        report = build_pit_replay_report(rows=rows, cutoffs=["2026-01-10"], write=False)

        self.assertEqual(first["row_id"], "revision_2")
        self.assertEqual(second["row_id"], "revision_2")
        self.assertEqual(report["deterministic_tiebreak_status"], "pass")

    def test_missing_timestamp_fields_and_empty_rows_are_blocked(self) -> None:
        missing = build_pit_replay_report(
            rows=[{"row_id": "bad", "feature_date": "2026-01-10", "prediction_cutoff_date": "2026-01-10"}],
            cutoffs=["2026-01-10"],
            write=False,
        )
        empty = build_pit_replay_report(rows=[], cutoffs=["2026-01-10"], write=False)

        self.assertEqual(missing["status"], "blocked")
        self.assertIn("missing_source_timestamp", missing["blocking_reasons"])
        self.assertIn("missing_asof_date", missing["blocking_reasons"])
        self.assertIn("missing_ingest_timestamp", missing["blocking_reasons"])
        self.assertEqual(empty["status"], "blocked")
        self.assertIn("managed_rows_missing", empty["blocking_reasons"])

    def test_replay_report_writes_manifest_without_triggering_v12_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False), patch(
            "sn_futures.services.feature_store_v12_service.build_feature_store_v12"
        ) as build_v12:
            report = run_pit_replay_harness(rows=[row("valid", "2026-01-09", "2026-01-09T09:00:00")], cutoffs=["2026-01-10"])
            report_text = Path(report["report_path"]).read_text(encoding="utf-8")

        build_v12.assert_not_called()
        self.assertEqual(report["status"], "ready")
        self.assertIn("pit_replay_v1", report_text)
        self.assertNotIn("Authorization", json.dumps(report, ensure_ascii=False) + report_text)


if __name__ == "__main__":
    unittest.main()
