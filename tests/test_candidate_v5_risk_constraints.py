from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

sys.path.insert(0, "src")

from sn_futures.services.multi_objective_research_optimizer import optimize_multi_objective_research_strategy


class CandidateV5RiskConstraintsTest(unittest.TestCase):
    def test_negative_2x_cost_stress_blocks_manual_approval_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            trace_dir = Path(tmp) / "outputs" / "walk_forward" / "v5"
            trace_dir.mkdir(parents=True, exist_ok=True)
            rows = []
            for idx in range(80):
                rows.append(
                    {
                        "candidate_version": "v5",
                        "dataset_version": "v5",
                        "horizon": "1d",
                        "fold_id": str(1 + idx // 20),
                        "label_start_time": f"2026-02-{min(idx % 28 + 1, 28):02d}",
                        "label_end_time": f"2026-02-{min(idx % 28 + 2, 28):02d}",
                        "realized_direction": 1,
                        "realized_return": 0.0001,
                        "predicted_direction": 1,
                        "confidence": 0.8,
                        "trade_edge": 0.001,
                        "cost_assumption": 0.0002,
                        "regime_label": "HIGH_VOL",
                    }
                )
            pd.DataFrame(rows).to_csv(trace_dir / "oof_trace_1d.csv", index=False, encoding="utf-8")
            result = optimize_multi_objective_research_strategy(candidate_version="v5", horizons=("1d",))

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["promotion_readiness"], "research_only")
        self.assertIn("2x_cost_stress_negative", result["blocking_reasons"])
        self.assertFalse(result["active_updated"])


if __name__ == "__main__":
    unittest.main()
