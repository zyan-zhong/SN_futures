from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.learning_scheduler_service import run_learning_scheduler_once


class LearningSchedulerNoAutoActiveTest(unittest.TestCase):
    def test_promotion_is_always_dry_run_and_active_registry_is_not_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            output = Path(tmp) / "outputs"
            with patch("sn_futures.services.learning_scheduler_service.run_institutional_refresh_steps", return_value={"status": "success"}), \
                patch("sn_futures.services.learning_scheduler_service.build_feature_store_v5", return_value={"status": "success"}), \
                patch("sn_futures.services.learning_scheduler_service.run_candidate_v5_research", return_value={"status": "success", "candidate_version": "v5"}), \
                patch("sn_futures.services.learning_scheduler_service.run_institutional_validation", return_value={"status": "success", "passed": True}), \
                patch("sn_futures.services.learning_scheduler_service.archive_research_run", return_value={"status": "success", "run_id": "run"}), \
                patch("sn_futures.services.learning_scheduler_service.promote_candidate") as promote:
                promote.return_value = {
                    "status": "passed",
                    "dry_run": True,
                    "active_updated": False,
                    "message_zh": "dry run only",
                }
                result = run_learning_scheduler_once(force=True)

            self.assertTrue(promote.called)
            self.assertTrue(promote.call_args.kwargs["dry_run"])
            self.assertTrue(result["manual_approval_required"])
            self.assertFalse(result["active_updated"])
            self.assertFalse((output / "model_registry" / "active_model.json").exists())
            self.assertFalse((output / "sn_live_predictions.json").exists())


if __name__ == "__main__":
    unittest.main()
