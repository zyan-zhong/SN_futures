from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.learning_scheduler_service import (
    pause_learning_scheduler,
    resume_learning_scheduler,
    run_learning_scheduler_once,
)


class LearningSchedulerArtifactsTest(unittest.TestCase):
    def test_scheduler_writes_history_artifact_reference_and_supports_pause_resume(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            artifact_dir = Path(tmp) / "outputs" / "research_runs" / "scheduler_artifact"
            with patch("sn_futures.services.learning_scheduler_service.run_institutional_refresh_steps", return_value={"status": "success"}), \
                patch("sn_futures.services.learning_scheduler_service.build_feature_store_v5", return_value={"status": "success"}), \
                patch("sn_futures.services.learning_scheduler_service.run_candidate_v5_research", return_value={"status": "success"}), \
                patch("sn_futures.services.learning_scheduler_service.run_institutional_validation", return_value={"status": "success"}), \
                patch("sn_futures.services.learning_scheduler_service.promote_candidate", return_value={"status": "rejected", "dry_run": True}), \
                patch("sn_futures.services.learning_scheduler_service.archive_research_run", return_value={"status": "success", "run_id": "scheduler_artifact", "artifact_dir": str(artifact_dir)}):
                pause = pause_learning_scheduler("maintenance")
                paused_run = run_learning_scheduler_once()
                resume = resume_learning_scheduler()
                result = run_learning_scheduler_once()

            self.assertTrue(pause["paused"])
            self.assertEqual(paused_run["status"], "paused")
            self.assertFalse(resume["paused"])
            self.assertEqual(result["artifact_run_id"], "scheduler_artifact")
            history_path = Path(tmp) / "outputs" / "learning_scheduler" / "learning_scheduler_history.json"
            history = json.loads(history_path.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(history["runs"]), 1)
            self.assertEqual(history["runs"][-1]["artifact_run_id"], "scheduler_artifact")


if __name__ == "__main__":
    unittest.main()
