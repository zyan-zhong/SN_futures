from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sn_futures.services.oof_integrity_service import build_oof_integrity_report
from test_oof_integrity_service import _write_manifest, _write_trace, _write_wf


def test_oof_trace_passes_basic_validation_window_checks() -> None:
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
        _write_manifest(tmp)
        _write_wf(tmp)
        _write_trace(tmp)

        report = build_oof_integrity_report()
        checks = report["horizons"]["1d"]["leakage_checks"]

        assert checks["fold_id_non_empty"] is True
        assert checks["records_match_validation_fold"] is True
        assert checks["timestamp_not_in_train_window"] is True
        assert checks["prediction_time_not_after_label_start"] is True


def test_duplicate_timestamp_fold_is_integrity_failure() -> None:
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
        _write_manifest(tmp)
        _write_wf(tmp)
        _write_trace(tmp)
        trace_path = Path(tmp) / "outputs" / "walk_forward" / "oof_trace_1d.csv"
        frame = pd.read_csv(trace_path)
        frame = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
        frame.to_csv(trace_path, index=False)

        report = build_oof_integrity_report()
        checks = report["horizons"]["1d"]["leakage_checks"]
        reasons = " ".join(report["horizons"]["1d"]["blocking_reasons"])

        assert checks["no_duplicate_timestamp_horizon_fold"] is False
        assert "no_duplicate_timestamp_horizon_fold" in reasons
