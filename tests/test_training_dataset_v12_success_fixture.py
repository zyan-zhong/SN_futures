from __future__ import annotations

import json
import math
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

import sys

sys.path.insert(0, "src")

from sn_futures.services.training_dataset_v12_service import build_training_dataset_v12


MANAGED_FIELDS = {
    "spot_price": 210000.0,
    "spot_premium": 100.0,
    "spot_futures_basis": 80.0,
    "shfe_inventory": 3000.0,
    "shfe_warehouse_receipt": 500.0,
    "lme_tin_close": 33000.0,
    "lme_inventory": 5000.0,
    "near_contract_close": 209900.0,
    "near_open_interest": 11000.0,
    "far_contract_close": 210700.0,
    "far_open_interest": 9000.0,
    "main_contract_switch_flag": 0.0,
}


def _write_ready_v12_feature_store(root: str, rows: int = 60) -> Path:
    output = Path(root) / "outputs"
    feature_dir = output / "feature_store" / "v12"
    feature_dir.mkdir(parents=True)
    records = []
    dates = pd.date_range("2026-01-01", periods=rows, freq="D")
    for idx, day in enumerate(dates):
        wave = math.sin(idx / 4.0)
        base = 210000.0 + idx * 120.0 + wave * 900.0
        record = {
            "trade_date": day.strftime("%Y-%m-%d"),
            "prediction_cutoff_date": day.strftime("%Y-%m-%d"),
            "close": base,
            "open": base - 80.0,
            "high": base + 200.0,
            "low": base - 220.0,
            "volume": 1000.0 + idx * 3.0,
            "atr_14": 100.0 + (idx % 9) * 10.0,
            "managed_asof_date": day.strftime("%Y-%m-%d"),
            "managed_source_timestamp": f"{day.strftime('%Y-%m-%d')}T09:00:00",
            "managed_ingest_timestamp": f"{day.strftime('%Y-%m-%d')}T10:00:00",
        }
        for name, value in MANAGED_FIELDS.items():
            record[name] = value + (idx % 17) * (7.0 if name != "main_contract_switch_flag" else 0.0)
        record["spot_futures_basis"] = -500.0 + idx * 18.0
        record["shfe_inventory"] = 2200.0 + (idx % 20) * 95.0
        record["shfe_warehouse_receipt"] = 300.0 + (idx % 15) * 35.0
        record["lme_inventory"] = 4500.0 - (idx % 22) * 60.0
        record["near_contract_close"] = base - 130.0
        record["far_contract_close"] = base + 70.0 + idx * 3.0
        record["near_open_interest"] = 9000.0 + (idx % 13) * 140.0
        record["far_open_interest"] = 7600.0 + (idx % 11) * 110.0
        records.append(record)
    csv_path = feature_dir / "feature_store.csv"
    pd.DataFrame(records).to_csv(csv_path, index=False)
    manifest = {
        "status": "ready",
        "feature_store_version": "v12",
        "feature_store_path": str(csv_path),
        "manifest_path": str(feature_dir / "feature_store_manifest.json"),
        "no_lookahead_pass": True,
        "point_in_time_join_ready": True,
        "managed_data_used": True,
        "fake_data_used": False,
        "mock_data_used": False,
        "managed_field_coverage": {"total": 12, "available": 12, "missing": 0, "ratio": 1.0, "label": "12/12"},
        "missing_fundamental_fields": [],
    }
    (feature_dir / "feature_store_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path


class TrainingDatasetV12SuccessFixtureTest(unittest.TestCase):
    def test_ready_feature_store_builds_all_horizon_datasets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_ready_v12_feature_store(tmp)
            result = build_training_dataset_v12()
            dataset_paths = dict(result["dataset_paths"])
            frames = {horizon: pd.read_parquet(path) for horizon, path in dataset_paths.items()}

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["dataset_version"], "v12")
        self.assertEqual(result["feature_store_version"], "v12")
        self.assertEqual(set(dataset_paths), {"1d", "3d", "5d", "10d", "20d"})
        self.assertTrue(all(Path(path).suffix == ".parquet" for path in dataset_paths.values()))
        self.assertTrue(all(not frame.empty for frame in frames.values()))
        for horizon, frame in frames.items():
            self.assertIn("train", set(frame["split"]))
            self.assertIn("validation", set(frame["split"]))
            self.assertGreater(len(set(frame["managed_regime_label"])), 1, horizon)
            self.assertAlmostEqual(float(frame["sample_weight"].mean()), 1.0, places=6)
            for column in (
                "horizon",
                "target_return",
                "target_direction",
                "split",
                "sample_weight",
                "technical_regime_label",
                "managed_regime_label",
                "managed_regime_sample_weight",
                "managed_basis_zscore",
                "inventory_zscore",
                "warehouse_receipt_zscore",
                "lme_shfe_inventory_spread",
                "near_far_carry",
                "open_interest_term_spread",
            ):
                self.assertIn(column, frame.columns)
        self.assertTrue(result["no_lookahead_pass"])
        self.assertTrue(result["point_in_time_join_ready"])
        self.assertFalse(result["training_invoked"])
        self.assertFalse(result["active_updated"])
        self.assertFalse(result["customer_prediction_generated"])


if __name__ == "__main__":
    unittest.main()
