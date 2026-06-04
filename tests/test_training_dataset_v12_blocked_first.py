from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys

sys.path.insert(0, "src")

from sn_futures.services.training_dataset_v12_service import build_training_dataset_v12, validate_training_dataset_v12_readiness


class TrainingDatasetV12BlockedFirstTest(unittest.TestCase):
    def test_missing_feature_store_manifest_writes_blocked_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
                result = build_training_dataset_v12()
                manifest_path = Path(result["manifest_path"])
                dataset_dir = Path(tmp) / "outputs" / "training_datasets" / "v12"
                manifest_exists = manifest_path.exists()

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["dataset_version"], "v12")
        self.assertEqual(result["feature_store_version"], "v12")
        self.assertTrue(manifest_exists)
        self.assertEqual(result["dataset_paths"], {})
        self.assertFalse(any(dataset_dir.glob("train_*.*")) if dataset_dir.exists() else False)
        self.assertIn("feature_store_v12_manifest_missing", result["blocked_reasons"])
        self.assertFalse(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])

    def test_blocked_feature_store_blocks_dataset_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            manifest_dir = Path(tmp) / "outputs" / "feature_store" / "v12"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "feature_store_manifest.json").write_text(
                json.dumps(
                    {
                        "status": "blocked",
                        "feature_store_version": "v12",
                        "feature_store_path": str(manifest_dir / "feature_store.csv"),
                        "no_lookahead_pass": False,
                        "point_in_time_join_ready": False,
                        "managed_field_coverage": {"total": 12, "available": 0, "ratio": 0.0, "label": "0/12"},
                        "blocking_reasons": ["managed_proxy_disabled"],
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = build_training_dataset_v12()

        self.assertEqual(result["status"], "blocked")
        self.assertEqual(result["feature_store_status"], "blocked")
        self.assertIn("feature_store_v12_blocked", result["blocked_reasons"])
        self.assertIn("managed_proxy_disabled", result["blocked_reasons"])
        self.assertEqual(result["dataset_paths"], {})

    def test_missing_feature_store_csv_blocks_dataset_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            manifest_dir = Path(tmp) / "outputs" / "feature_store" / "v12"
            manifest_dir.mkdir(parents=True)
            (manifest_dir / "feature_store_manifest.json").write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "feature_store_version": "v12",
                        "feature_store_path": str(manifest_dir / "feature_store.csv"),
                        "no_lookahead_pass": True,
                        "point_in_time_join_ready": True,
                        "managed_field_coverage": {"total": 12, "available": 12, "ratio": 1.0, "label": "12/12"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            result = build_training_dataset_v12()

        self.assertEqual(result["status"], "blocked")
        self.assertIn("feature_store_v12_csv_missing", result["blocked_reasons"])

    def test_failed_pit_or_no_lookahead_blocks_dataset_v12(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            manifest_dir = Path(tmp) / "outputs" / "feature_store" / "v12"
            manifest_dir.mkdir(parents=True)
            csv_path = manifest_dir / "feature_store.csv"
            csv_path.write_text("trade_date,close\n2026-01-01,210000\n", encoding="utf-8")
            (manifest_dir / "feature_store_manifest.json").write_text(
                json.dumps(
                    {
                        "status": "ready",
                        "feature_store_version": "v12",
                        "feature_store_path": str(csv_path),
                        "no_lookahead_pass": False,
                        "point_in_time_join_ready": False,
                        "managed_field_coverage": {"total": 12, "available": 12, "ratio": 1.0, "label": "12/12"},
                    },
                    ensure_ascii=False,
                ),
                encoding="utf-8",
            )
            readiness = validate_training_dataset_v12_readiness()

        self.assertEqual(readiness["status"], "blocked")
        self.assertIn("feature_store_v12_no_lookahead_failed", readiness["blocked_reasons"])
        self.assertIn("feature_store_v12_pit_join_not_ready", readiness["blocked_reasons"])


if __name__ == "__main__":
    unittest.main()
