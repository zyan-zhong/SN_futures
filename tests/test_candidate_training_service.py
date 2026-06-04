from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.governance.model_registry import ModelRegistry
from sn_futures.api.terminal_api import handle_terminal_api
from sn_futures.services.training_dataset_service import build_training_dataset
from sn_futures.services.walk_forward_training_service import run_candidate_training


def _write_history(root: str, rows: int = 220) -> None:
    output = Path(root) / "outputs"
    output.mkdir(parents=True, exist_ok=True)
    history = []
    for idx, day in enumerate(pd.date_range("2024-01-01", periods=rows, freq="D")):
        close = 210000.0 + idx * 65.0 + (idx % 7) * 180.0
        history.append(
            {
                "time": day.strftime("%Y-%m-%d"),
                "open": close - 180,
                "high": close + 520,
                "low": close - 520,
                "close": close,
                "volume": 8000 + idx,
            }
        )
    (output / "sn_market_history.json").write_text(json.dumps({"history": history}, ensure_ascii=False), encoding="utf-8")


class CandidateTrainingServiceTest(unittest.TestCase):
    def test_candidate_training_writes_metrics_registry_and_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            build_training_dataset(horizons=(1,), min_feature_coverage=0.7)
            result = run_candidate_training(["1d"])
            self.assertEqual(result["status"], "success")
            self.assertFalse(result["candidate_is_active"])
            self.assertFalse(result["active_updated"])
            self.assertFalse(result["customer_prediction_generated"])
            metrics = result["metrics_by_horizon"]["1d"]
            for key in ["directional_accuracy", "balanced_accuracy", "brier_score", "calibration_error", "return_mae", "return_rmse", "fold_count", "sample_count"]:
                self.assertIn(key, metrics)
            registry_path = Path(result["registry_path"])
            self.assertTrue(registry_path.exists())
            registry = ModelRegistry(registry_path)
            candidates = registry.list_candidates("1d")
            self.assertEqual(len(candidates), 1)
            self.assertIsNone(registry.get_active_model("1d"))
            self.assertTrue(Path(candidates[0].artifact_path).exists())

    def test_candidate_training_api_and_docs_are_available(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_history(tmp)
            build_training_dataset(horizons=(1,), min_feature_coverage=0.7)
            status, payload = handle_terminal_api(
                "/api/terminal/models/train-candidate",
                "POST",
                body={"horizons": ["1d"]},
            )
            self.assertEqual(status, 200)
            self.assertEqual(payload["kind"], "train_candidate")
            self.assertIn("task_id", payload)
            self.assertNotIn("candidate_is_active", payload)
            self._wait_for_task(str(payload["task_id"]))
            status, wf = handle_terminal_api("/api/terminal/models/walk-forward-results", "GET")
            self.assertEqual(status, 200)
            self.assertIn("1d", wf["results"])
            status, docs = handle_terminal_api("/api/terminal/docs", "GET")
            self.assertEqual(status, 200)
            dumped = json.dumps(docs, ensure_ascii=False)
            self.assertIn("/api/terminal/models/train-candidate", dumped)
            self.assertIn("/api/terminal/models/candidate-status", dumped)
            self.assertIn("/api/terminal/models/walk-forward-results", dumped)

    def _wait_for_task(self, task_id: str) -> None:
        for _ in range(80):
            _, payload = handle_terminal_api("/api/terminal/tasks/status", "GET", query={"id": [task_id]})
            if payload.get("status") in {"success", "failed"}:
                time.sleep(0.1)
                return
            time.sleep(0.05)


if __name__ == "__main__":
    unittest.main()
