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


class NoActiveWrittenByDryRunTest(unittest.TestCase):
    def test_dry_run_does_not_modify_existing_active_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ, {"SN_DATA_DIR": tmp}, clear=False):
            active_path = Path(tmp) / "outputs" / "model_registry" / "active_model.json"
            active_path.parent.mkdir(parents=True, exist_ok=True)
            original = {"status": "active_available", "active_models": [{"model_id": "existing"}]}
            active_path.write_text(json.dumps(original, ensure_ascii=False), encoding="utf-8")

            report = promote_candidate(candidate_version="v2", dry_run=True)
            current = json.loads(active_path.read_text(encoding="utf-8"))

            self.assertFalse(report["active_updated"])
            self.assertEqual(current, original)


if __name__ == "__main__":
    unittest.main()
