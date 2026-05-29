from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, "src")

from sn_futures.services.model_promotion_service import promote_candidate
from test_model_promotion_service import _write_candidate_state


class NoBaselinePromotionTest(unittest.TestCase):
    def test_baseline_used_manifest_cannot_promote(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            _write_candidate_state(tmp, manifest_updates={"baseline_used": True})
            report = promote_candidate()
            self.assertFalse(report["passed"])
            self.assertFalse((Path(tmp) / "outputs" / "model_registry" / "active_model.json").exists())
            self.assertIn("baseline 不可晋级为 active", json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    unittest.main()
