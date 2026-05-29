from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from sn_futures.services.oof_integrity_service import build_oof_integrity_report
from test_oof_integrity_service import _write_manifest, _write_trace, _write_wf


def test_single_fold_concentration_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
        _write_manifest(tmp)
        _write_wf(tmp)
        _write_trace(tmp, dominant_fold=True)

        report = build_oof_integrity_report()
        reasons = " ".join(report["horizons"]["1d"]["blocking_reasons"])

        assert "fold" in reasons


def test_negative_cost_adjusted_expectancy_is_blocked() -> None:
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
        _write_manifest(tmp)
        _write_wf(tmp)
        _write_trace(tmp, negative_expectancy=True)

        report = build_oof_integrity_report()
        reasons = " ".join(report["horizons"]["1d"]["blocking_reasons"])

        assert "期望" in reasons or "鏈" in reasons


def test_small_high_confidence_sample_adds_warning() -> None:
    with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
        _write_manifest(tmp)
        _write_wf(tmp)
        _write_trace(tmp, rows_per_fold=8)

        report = build_oof_integrity_report()
        warnings = " ".join(report["horizons"]["1d"]["warnings"])

        assert "样本" in warnings or "鏍锋湰" in warnings
