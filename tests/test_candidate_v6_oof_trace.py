from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")
sys.path.insert(0, "tests")

from candidate_v6_research_fixtures import successful_candidate, successful_dataset, write_ready_v6_inputs
from sn_futures.services.candidate_v6_gated_research_service import run_candidate_v6_gated_research


class CandidateV6OOFTraceTest(unittest.TestCase):
    def test_ready_pipeline_preserves_v6_oof_trace_artifact_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            write_ready_v6_inputs(output)

            def fake_training(**_: object) -> dict[str, object]:
                trace_path = output / "walk_forward" / "v6" / "oof_trace_1d.csv"
                trace_path.parent.mkdir(parents=True, exist_ok=True)
                trace_path.write_text(
                    "timestamp,label_start_time,label_end_time,horizon,fold_id,predicted_direction,realized_direction,realized_return,confidence,trade_edge,cost_assumption\n"
                    "2026-05-01,2026-05-01,2026-05-02,1d,1,1,1,0.01,0.8,0.002,0.0002\n",
                    encoding="utf-8",
                )
                return successful_candidate(output)

            with patch("sn_futures.services.candidate_v6_gated_research_service.build_training_dataset", return_value=successful_dataset()), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_candidate_training", side_effect=fake_training), \
                patch("sn_futures.services.candidate_v6_gated_research_service.get_oof_integrity_report", return_value={"status": "success", "candidate_version": "v6"}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_research_backtest", return_value={"status": "success"}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.run_institutional_validation", return_value={"status": "failed", "passed": False, "dry_run": True}), \
                patch("sn_futures.services.candidate_v6_gated_research_service.promote_candidate", return_value={"status": "failed", "passed": False, "dry_run": True, "active_updated": False}):
                result = run_candidate_v6_gated_research(horizons=("1d",))

            trace_path = output / "walk_forward" / "v6" / "oof_trace_1d.csv"
            self.assertTrue(trace_path.exists())
            self.assertEqual(result["candidate"]["oof_trace_paths"]["1d"], str(trace_path))
            self.assertEqual(result["oof_integrity"]["candidate_version"], "v6")


if __name__ == "__main__":
    unittest.main()
